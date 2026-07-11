import os
from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKENS_DIR = os.path.join(BASE_DIR, "tokens")
DB_PATH = os.path.join(BASE_DIR, "mail_agent.db")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

# --- Gmail API ---
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

# --- AI Providers ---
GEMINI_API_KEY = "AIzaSyB7UmQqBETJu3d3uUo4KU0E4-xHtZnW-QU"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "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")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NIM_MODEL = os.getenv("NIM_MODEL", "meta/llama-3.1-8b-instruct")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "qwen3.5-4b")

# --- Flask ---
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

# --- Sync ---
MAX_EMAILS_PER_SYNC = int(os.getenv("MAX_EMAILS_PER_SYNC", "50"))

# Ensure tokens directory exists
os.makedirs(TOKENS_DIR, exist_ok=True)
