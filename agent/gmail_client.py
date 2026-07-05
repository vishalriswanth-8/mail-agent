"""
Gmail API Client — Read, Send, and Manage Emails.
Wraps the Gmail API with clean methods for the agent.
"""

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build

from agent.auth_manager import AuthManager


class GmailClient:
    """Interface to Gmail API for reading and sending emails."""

    def __init__(self, auth_manager: AuthManager):
        self.auth = auth_manager
        self._services = {}  # Cache services per account

    def _get_service(self, email: str):
        """Get or create a Gmail API service for the given account."""
        if email not in self._services:
            creds = self.auth.get_credentials(email)
            if not creds:
                raise ValueError(f"No valid credentials for {email}")
            self._services[email] = build("gmail", "v1", credentials=creds)
        return self._services[email]

    def fetch_emails(
        self, email: str, max_results: int = 50, query: str = ""
    ) -> list[dict]:
        """
        Fetch emails from an account's inbox.
        Returns list of email metadata dicts.
        """
        service = self._get_service(email)
        query = query or "in:inbox"

        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
        except Exception as e:
            print(f"[GmailClient] Error fetching emails for {email}: {e}")
            return []

        messages = results.get("messages", [])
        emails = []

        for msg_meta in messages:
            try:
                email_data = self.get_email_detail(email, msg_meta["id"])
                if email_data:
                    emails.append(email_data)
            except Exception as e:
                print(f"[GmailClient] Error fetching email {msg_meta['id']}: {e}")
                continue

        return emails

    def get_email_detail(self, account_email: str, msg_id: str) -> dict | None:
        """Get full details of a single email."""
        service = self._get_service(account_email)

        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
        except Exception as e:
            print(f"[GmailClient] Error getting email detail: {e}")
            return None

        headers = msg.get("payload", {}).get("headers", [])
        header_dict = {h["name"].lower(): h["value"] for h in headers}

        # Extract body
        body = self._extract_body(msg.get("payload", {}))

        # Determine if read
        labels = msg.get("labelIds", [])
        is_read = "UNREAD" not in labels

        return {
            "id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "subject": header_dict.get("subject", "(No Subject)"),
            "sender": header_dict.get("from", "Unknown"),
            "to": header_dict.get("to", ""),
            "date": header_dict.get("date", ""),
            "snippet": msg.get("snippet", ""),
            "body": body,
            "is_read": is_read,
            "labels": labels,
            "internal_date": msg.get("internalDate", "0"),
        }

    def _extract_body(self, payload: dict) -> str:
        """Extract email body text from payload (handles multipart)."""
        body_text = ""

        if "body" in payload and payload["body"].get("data"):
            body_text = base64.urlsafe_b64decode(
                payload["body"]["data"]
            ).decode("utf-8", errors="replace")

        elif "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain" and part.get("body", {}).get("data"):
                    body_text = base64.urlsafe_b64decode(
                        part["body"]["data"]
                    ).decode("utf-8", errors="replace")
                    break
                elif mime_type == "text/html" and not body_text:
                    if part.get("body", {}).get("data"):
                        body_text = base64.urlsafe_b64decode(
                            part["body"]["data"]
                        ).decode("utf-8", errors="replace")
                elif mime_type.startswith("multipart/"):
                    # Recursively handle nested multipart
                    body_text = self._extract_body(part)
                    if body_text:
                        break

        return body_text

    def send_email(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        is_html: bool = False,
    ) -> dict:
        """Send an email from the specified account."""
        service = self._get_service(from_email)

        message = MIMEMultipart()
        message["to"] = to_email
        message["from"] = from_email
        message["subject"] = subject

        content_type = "html" if is_html else "plain"
        message.attach(MIMEText(body, content_type))

        raw_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("utf-8")

        try:
            sent = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": raw_message})
                .execute()
            )
            print(f"[GmailClient] Email sent from {from_email} to {to_email}")
            return {"success": True, "message_id": sent.get("id", "")}
        except Exception as e:
            print(f"[GmailClient] Error sending email: {e}")
            return {"success": False, "error": str(e)}

    def mark_as_read(self, account_email: str, msg_id: str) -> bool:
        """Mark an email as read."""
        service = self._get_service(account_email)
        try:
            service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
            return True
        except Exception as e:
            print(f"[GmailClient] Error marking as read: {e}")
            return False

    def get_profile(self, email: str) -> dict:
        """Get the Gmail profile for an account."""
        service = self._get_service(email)
        try:
            profile = service.users().getProfile(userId="me").execute()
            return {
                "email": profile.get("emailAddress", email),
                "messages_total": profile.get("messagesTotal", 0),
                "threads_total": profile.get("threadsTotal", 0),
            }
        except Exception as e:
            print(f"[GmailClient] Error getting profile: {e}")
            return {"email": email, "messages_total": 0, "threads_total": 0}

    def invalidate_cache(self, email: str = None):
        """Clear cached services (useful after token refresh)."""
        if email:
            self._services.pop(email, None)
        else:
            self._services.clear()
