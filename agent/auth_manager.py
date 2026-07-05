"""
OAuth2 Authentication Manager for Multiple Gmail Accounts.
Handles per-account token storage, refresh, and consent flows.
Supports both "web" and "installed" (desktop) OAuth client types.
"""

import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import config

# Fixed port for OAuth redirect — must match Google Cloud Console
OAUTH_PORT = 8090
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_PORT}/"


class AuthManager:
    """Manages OAuth2 credentials for multiple Gmail accounts."""

    def __init__(self):
        self.tokens_dir = config.TOKENS_DIR
        self.scopes = config.GMAIL_SCOPES
        self.credentials_file = config.CREDENTIALS_FILE

    def _token_path(self, email: str) -> str:
        """Get the token file path for a specific email account."""
        safe_name = email.replace("@", "_at_").replace(".", "_dot_")
        return os.path.join(self.tokens_dir, f"token_{safe_name}.json")

    def _load_client_config(self) -> dict:
        """
        Load credentials.json and normalize it to 'installed' format.
        Google Cloud Console may export 'web' type credentials, but
        InstalledAppFlow requires 'installed' format.
        """
        with open(self.credentials_file, "r") as f:
            raw = json.load(f)

        # If already "installed" type, return as-is
        if "installed" in raw:
            # Ensure redirect_uris includes our fixed port
            if "redirect_uris" not in raw["installed"]:
                raw["installed"]["redirect_uris"] = [OAUTH_REDIRECT_URI]
            return raw

        # Convert "web" type to "installed" format
        if "web" in raw:
            web = raw["web"]
            installed_config = {
                "installed": {
                    "client_id": web["client_id"],
                    "client_secret": web["client_secret"],
                    "project_id": web.get("project_id", ""),
                    "auth_uri": web.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
                    "token_uri": web.get("token_uri", "https://oauth2.googleapis.com/token"),
                    "auth_provider_x509_cert_url": web.get(
                        "auth_provider_x509_cert_url",
                        "https://www.googleapis.com/oauth2/v1/certs",
                    ),
                    "redirect_uris": [OAUTH_REDIRECT_URI],
                }
            }
            return installed_config

        raise ValueError(
            "Invalid credentials.json format. Expected 'web' or 'installed' key."
        )

    def get_credentials(self, email: str) -> Credentials | None:
        """Load and auto-refresh credentials for an account."""
        token_path = self._token_path(email)
        if not os.path.exists(token_path):
            return None

        creds = Credentials.from_authorized_user_file(token_path, self.scopes)

        # Auto-refresh if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(email, creds)
            except Exception as e:
                print(f"[AuthManager] Failed to refresh token for {email}: {e}")
                return None

        return creds

    def _save_credentials(self, email: str, creds: Credentials):
        """Save credentials to the token file."""
        token_path = self._token_path(email)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    def add_account(self) -> str:
        """
        Initiate OAuth consent flow. Opens browser for user to authorize.
        Uses a fixed port (8090) so the redirect URI is predictable.
        Returns the authenticated email address.
        """
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(
                f"credentials.json not found at {self.credentials_file}. "
                "Download it from Google Cloud Console."
            )

        # Load and normalize client config (handles web -> installed conversion)
        client_config = self._load_client_config()

        flow = InstalledAppFlow.from_client_config(client_config, self.scopes)
        creds = flow.run_local_server(port=OAUTH_PORT)

        # Build a temporary Gmail service to get the email address
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email = profile["emailAddress"]

        # Save the token
        self._save_credentials(email, creds)
        print(f"[AuthManager] Account added: {email}")
        return email

    def list_accounts(self) -> list[dict]:
        """List all authenticated accounts with their status."""
        accounts = []
        if not os.path.exists(self.tokens_dir):
            return accounts

        for filename in os.listdir(self.tokens_dir):
            if filename.startswith("token_") and filename.endswith(".json"):
                filepath = os.path.join(self.tokens_dir, filename)
                try:
                    creds = Credentials.from_authorized_user_file(
                        filepath, self.scopes
                    )
                    # Extract email from token file
                    with open(filepath, "r") as f:
                        token_data = json.load(f)

                    # Try to get email - build service if needed
                    email = token_data.get("client_id", "unknown")

                    # Better: derive from filename
                    name_part = filename.replace("token_", "").replace(".json", "")
                    email = name_part.replace("_at_", "@").replace("_dot_", ".")

                    is_valid = creds.valid or (
                        creds.expired and creds.refresh_token is not None
                    )

                    accounts.append(
                        {
                            "email": email,
                            "is_valid": is_valid,
                            "is_expired": creds.expired if creds else True,
                        }
                    )
                except Exception as e:
                    print(f"[AuthManager] Error reading {filename}: {e}")

        return accounts

    def remove_account(self, email: str) -> bool:
        """Remove an account's token file."""
        token_path = self._token_path(email)
        if os.path.exists(token_path):
            os.remove(token_path)
            print(f"[AuthManager] Account removed: {email}")
            return True
        return False

    def is_authenticated(self, email: str) -> bool:
        """Check if an account has valid credentials."""
        creds = self.get_credentials(email)
        return creds is not None and (
            creds.valid or (creds.expired and creds.refresh_token)
        )
