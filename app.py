"""
Gmail Agent — Flask Application & REST API.
Serves the dashboard and provides API endpoints for email management.
"""

import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request

import config
from agent.auth_manager import AuthManager
from agent.gmail_client import GmailClient
from agent.ai_engine import AIEngine
from agent.db_manager import DBManager
from agent.autonomous_agent import AutonomousAgent

# --- Initialize Components ---
app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

# --- Enable CORS globally for local API access ---
@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        headers = response.headers
        headers["Access-Control-Allow-Origin"] = "*"
        headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        headers["Access-Control-Allow-Private-Network"] = "true"
        return response

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response



auth_manager = AuthManager()
gmail_client = GmailClient(auth_manager)
ai_engine = AIEngine()
db = DBManager()
agent = AutonomousAgent()

# Track sync progress
sync_status = {"is_syncing": False, "current": 0, "total": 0, "account": "", "message": ""}

# Background sync thread tracking
_sync_thread = None
_auto_sync_enabled = False
_auto_sync_interval = 10  # seconds

# Background scheduler thread
_scheduler_running = True
_scheduler_thread = None

# Incoming monitor thread
_monitor_running = True
_monitor_thread = None

AI_SETTING_KEYS = {
    "ai_provider",
    "local_base_url",
    "local_model",
    "cloud_provider",
    "cloud_model",
    "force_provider",
}


def get_ai_settings() -> dict:
    """Return AI settings merged with provider defaults."""
    stored = {
        "ai_provider": db.get_setting("ai_provider", ""),
        "local_base_url": db.get_setting("local_base_url", config.LMSTUDIO_BASE_URL),
        "local_model": db.get_setting("local_model", ""),
        "cloud_provider": db.get_setting("cloud_provider", "nim"),
        "cloud_model": db.get_setting("cloud_model", config.NIM_MODEL),
        "force_provider": db.get_setting("force_provider", "false").lower() == "true",
    }
    return ai_engine.resolve_settings(stored)


def _fetch_scope_emails(scope: str = "all", account: str | None = None, email_id: int | None = None, limit: int = 50) -> list[dict]:
    """Collect email rows for chat/task context."""
    if email_id:
        row = db.get_email_by_id(email_id)
        return [row] if row else []

    if scope == "thread" and account and email_id:
        row = db.get_email_by_id(email_id)
        if not row:
            return []
        thread_id = row.get("thread_id")
        if not thread_id:
            return [row]
        rows = db.get_emails(account=account, limit=limit * 2)
        return [email for email in rows if email.get("thread_id") == thread_id][:limit]

    return db.get_emails(account=account or None, limit=limit)


# ============================================================
# Background: Email Sync
# ============================================================

def _do_sync_for_accounts(accounts: list, show_already_processed: bool = True):
    """Background sync function for email accounts."""
    global sync_status
    sync_status = {"is_syncing": True, "current": 0, "total": 0, "account": "", "message": "Starting sync..."}

    try:
        for acc in accounts:
            email = acc["email"]
            sync_status["account"] = email
            sync_status["message"] = f"Fetching emails from {email}..."

            print(f"[Sync] Starting sync for {email}")

            try:
                emails = gmail_client.fetch_emails(email, max_results=config.MAX_EMAILS_PER_SYNC)
                print(f"[Sync] Fetched {len(emails)} emails from {email}")
            except Exception as e:
                print(f"[Sync] Error fetching {email}: {e}")
                sync_status["message"] = f"Error fetching {email}: {str(e)}"
                db.log_event("sync_error", f"Failed to fetch emails for {email}", {"error": str(e)})
                continue

            sync_status["total"] = len(emails)
            sync_status["current"] = 0
            ai_settings = get_ai_settings()

            for i, email_data in enumerate(emails):
                sync_status["current"] = i + 1
                sync_status["message"] = f"Processing {i + 1}/{len(emails)} from {email}..."

                existing = db.get_email_by_gmail_id(email, email_data["id"])
                if existing and existing.get("summary"):
                    if not show_already_processed:
                        continue
                    db.save_email(email, email_data, {
                        "priority": existing["priority"],
                        "priority_score": existing.get("priority_score", 3),
                        "category": existing["category"],
                        "summary": existing["summary"],
                        "short_summary": existing.get("short_summary", ""),
                        "is_important": bool(existing.get("is_important", False)),
                    })
                    continue

                try:
                    print(f"[Sync] Processing email {i+1}/{len(emails)}: {email_data.get('subject', '(no subject)')[:50]}")
                    ai_result = ai_engine.process_email(
                        subject=email_data.get("subject", ""),
                        body=email_data.get("body", ""),
                        sender=email_data.get("sender", ""),
                        settings=ai_settings,
                    )
                    print(f"[Sync]   -> {ai_settings.get('ai_provider', 'unknown')} model: priority={ai_result.get('priority', '?')}, category={ai_result.get('category', 'unknown')}")
                except Exception as e:
                    print(f"[Sync] ERROR processing email: {e}")
                    ai_result = {
                        "priority": "normal",
                        "priority_score": 3,
                        "category": "other",
                        "short_summary": "Could not summarize.",
                        "summary": "Error: Could not categorize this email.",
                        "key_points": [],
                        "action_items": [],
                        "is_important": False,
                    }

                db.save_email(email, email_data, ai_result)

            db.update_last_synced(email)
            db.log_event("sync_complete", f"Synced {len(emails)} emails for {email}", {"account": email, "count": len(emails)})
            print(f"[Sync] Completed sync for {email}")

        sync_status["message"] = "Sync complete!"
        print("[Sync] All accounts synced successfully")
    except Exception as e:
        sync_status["message"] = f"Sync error: {str(e)}"
        print(f"[Sync] Error: {e}")
        db.log_event("sync_error", f"Sync error: {str(e)}", {"error": str(e)})
    finally:
        sync_status["is_syncing"] = False


def _auto_sync_thread():
    """Background thread that periodically syncs emails."""
    global _auto_sync_enabled, _sync_thread

    while _auto_sync_enabled:
        try:
            if not sync_status["is_syncing"]:
                accounts = auth_manager.list_accounts()
                if accounts:
                    print(f"[AutoSync] Starting periodic sync for {len(accounts)} account(s)")
                    _do_sync_for_accounts(accounts, show_already_processed=False)
        except Exception as e:
            print(f"[AutoSync] Error: {e}")

        for _ in range(_auto_sync_interval):
            if not _auto_sync_enabled:
                break
            time.sleep(1)

    print("[AutoSync] Auto-sync thread stopped")
    _sync_thread = None


# ============================================================
# Background: Scheduled Email Sender
# ============================================================

def _scheduler_loop():
    """Background thread that sends scheduled emails when due."""
    global _scheduler_running
    print("[Scheduler] Email scheduler started")

    while _scheduler_running:
        try:
            pending = db.get_pending_scheduled_emails()
            for sch in pending:
                try:
                    result = gmail_client.send_email(
                        from_email=sch["from_email"],
                        to_email=sch["to_email"],
                        subject=sch["subject"],
                        body=sch["body"],
                    )
                    if result.get("success"):
                        db.update_scheduled_email_status(sch["id"], "sent")
                        db.log_event(
                            "email_sent",
                            f"Scheduled email sent to {sch['to_email']}",
                            {"subject": sch["subject"], "to": sch["to_email"], "from": sch["from_email"]},
                        )
                        print(f"[Scheduler] Sent scheduled email to {sch['to_email']}: {sch['subject']}")
                    else:
                        err = result.get("error", "Unknown error")
                        db.update_scheduled_email_status(sch["id"], "failed", err)
                        db.log_event("email_error", f"Failed to send scheduled email: {err}",
                                     {"subject": sch["subject"], "to": sch["to_email"]})
                except Exception as e:
                    db.update_scheduled_email_status(sch["id"], "failed", str(e))
                    db.log_event("email_error", f"Scheduler exception: {str(e)}", {"id": sch["id"]})
                    print(f"[Scheduler] Error sending scheduled email: {e}")
        except Exception as e:
            print(f"[Scheduler] Loop error: {e}")

        time.sleep(30)  # Check every 30 seconds

    print("[Scheduler] Scheduler stopped")


# ============================================================
# Background: Incoming Email Monitor (Auto-reply rules)
# ============================================================

_last_monitored_ids: set = set()


def _monitor_loop():
    """Background thread that monitors for new emails and applies auto-reply rules."""
    global _monitor_running, _last_monitored_ids
    print("[Monitor] Incoming email monitor started")

    # Initialize with existing email IDs to avoid replying to old emails
    existing = db.get_emails(limit=200)
    _last_monitored_ids = {e["gmail_id"] for e in existing if e.get("gmail_id")}

    while _monitor_running:
        try:
            rules = db.get_rules(active_only=True)
            ai_settings = get_ai_settings()
            persona = db.get_setting("agent_persona", "")
            accounts = auth_manager.list_accounts()

            for acc in accounts:
                email_addr = acc["email"]
                try:
                    recent = gmail_client.fetch_emails(email_addr, max_results=10)
                    for email_data in recent:
                        gmail_id = email_data.get("id", "")
                        if gmail_id in _last_monitored_ids:
                            continue

                        _last_monitored_ids.add(gmail_id)

                        # Save the email first
                        try:
                            ai_result = ai_engine.process_email(
                                subject=email_data.get("subject", ""),
                                body=email_data.get("body", ""),
                                sender=email_data.get("sender", ""),
                                settings=ai_settings,
                            )
                        except Exception:
                            ai_result = {"priority": "normal", "priority_score": 3,
                                         "category": "other", "short_summary": "", "summary": ""}

                        db.save_email(email_addr, email_data, ai_result)
                        db_email = db.get_email_by_gmail_id(email_addr, gmail_id)

                        if not db_email:
                            continue

                        # Process through rules + importance
                        result = agent.process_incoming_email(db_email, rules, settings=ai_settings, persona=persona)

                        # Mark important if detected
                        if result["is_important"]:
                            db.mark_important(db_email["id"], True)
                            db.log_event(
                                "importance_detected",
                                f"Email marked important: {email_data.get('subject', '')}",
                                {"email_id": db_email["id"], "reason": result["importance_reason"]},
                            )
                            print(f"[Monitor] Marked important: {email_data.get('subject', '')}")

                        # Execute auto-reply if rule matched
                        if result["matched_rule"] and result["reply_text"]:
                            rule_id = result["matched_rule"]
                            reply_text = result["reply_text"]

                            # Find sender email to reply to
                            sender_raw = email_data.get("sender", "")
                            to_addr = sender_raw
                            if "<" in sender_raw and ">" in sender_raw:
                                to_addr = sender_raw.split("<")[1].split(">")[0]

                            send_result = gmail_client.send_email(
                                from_email=email_addr,
                                to_email=to_addr,
                                subject=f"Re: {email_data.get('subject', '')}",
                                body=reply_text,
                            )

                            if send_result.get("success"):
                                db.record_rule_trigger(rule_id)
                                
                                # Save auto-reply to DB so it shows up in the dashboard
                                auto_reply_email_data = {
                                    "id": f"auto-reply-{int(time.time())}",
                                    "thread_id": email_data.get("thread_id", ""),
                                    "subject": f"Re: {email_data.get('subject', '')}",
                                    "sender": f"Auto-Reply <{email_addr}>",
                                    "to": to_addr,
                                    "date": datetime.now(timezone.utc).isoformat(),
                                    "snippet": reply_text[:100],
                                    "body": reply_text,
                                    "is_read": True,
                                }
                                auto_reply_ai_result = {
                                    "priority": "normal",
                                    "priority_score": 3,
                                    "category": "auto-reply",
                                    "short_summary": "Auto-reply sent via rule.",
                                    "summary": reply_text,
                                    "is_important": True
                                }
                                db.save_email(email_addr, auto_reply_email_data, auto_reply_ai_result)
                                db.log_event(
                                    "auto_reply_sent",
                                    f"Auto-reply sent to {to_addr}",
                                    {"rule_id": rule_id, "to": to_addr,
                                     "subject": email_data.get("subject", ""), "reply": reply_text},
                                )
                                print(f"[Monitor] Auto-reply sent to {to_addr} (rule {rule_id})")

                except Exception as e:
                    print(f"[Monitor] Error checking {email_addr}: {e}")

        except Exception as e:
            print(f"[Monitor] Loop error: {e}")

        time.sleep(60)  # Check every 60 seconds

    print("[Monitor] Monitor stopped")


# ============================================================
# Pages
# ============================================================

@app.route("/")
def index():
    """Serve the main dashboard."""
    return render_template("index.html")


@app.route("/dashboard")
def dashboard_pro():
    """Serve the professional dashboard with agent and chat features."""
    return render_template("dashboard-pro.html")


# ============================================================
# Account API
# ============================================================

@app.route("/api/accounts", methods=["GET"])
def list_accounts():
    """List all connected Gmail accounts."""
    try:
        token_accounts = auth_manager.list_accounts()
        db_accounts = db.get_accounts()
        db_map = {a["email"]: a for a in db_accounts}

        accounts = []
        for ta in token_accounts:
            email = ta["email"]
            db_info = db_map.get(email, {})
            accounts.append({
                "email": email,
                "is_valid": ta["is_valid"],
                "last_synced": db_info.get("last_synced", None),
                "total_messages": db_info.get("total_messages", 0),
                "display_name": db_info.get("display_name", email),
            })

        return jsonify({"accounts": accounts})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/accounts/add", methods=["POST"])
def add_account():
    """Start OAuth flow to add a new Gmail account."""
    try:
        email = auth_manager.add_account()
        db.add_account(email)

        try:
            profile = gmail_client.get_profile(email)
            db.add_account(email, profile.get("email", email))
        except Exception as pe:
            print(f"[API] Warning: Profile check failed: {pe}")

        db.log_event("account_added", f"Account added: {email}", {"email": email})
        return jsonify({"success": True, "email": email})
    except FileNotFoundError as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/accounts/<email>", methods=["DELETE"])
def remove_account(email):
    """Remove a connected account."""
    auth_manager.remove_account(email)
    db.remove_account(email)
    gmail_client.invalidate_cache(email)
    db.log_event("account_removed", f"Account removed: {email}", {"email": email})
    return jsonify({"success": True})


# ============================================================
# Email API
# ============================================================

@app.route("/api/emails", methods=["GET"])
def get_emails():
    """Get emails with optional filters."""
    account = request.args.get("account")
    category = request.args.get("category")
    priority_score = request.args.get("priority_score")
    search = request.args.get("search")
    is_read = request.args.get("is_read")
    is_important = request.args.get("is_important")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    if is_read is not None:
        is_read = is_read.lower() == "true"
    if is_important is not None:
        is_important = is_important.lower() == "true"

    emails = db.get_emails(
        account=account,
        category=category,
        priority_score=priority_score,
        is_read=is_read,
        is_important=is_important,
        search=search,
        limit=limit,
        offset=offset,
    )

    for email in emails:
        email.pop("body", None)

    return jsonify({"emails": emails, "count": len(emails)})


@app.route("/api/emails/<int:email_id>", methods=["GET"])
def get_email_detail(email_id):
    """Get full email details including body."""
    email = db.get_email_by_id(email_id)
    if not email:
        return jsonify({"error": "Email not found"}), 404

    if not email["is_read"]:
        db.mark_read(email_id)
        try:
            gmail_client.mark_as_read(email["account"], email["gmail_id"])
        except Exception:
            pass

    return jsonify({"email": email})


@app.route("/api/contacts/search", methods=["GET"])
def search_contacts():
    """Search for unique senders matching a name."""
    query = request.args.get("q", "")
    if not query:
        return jsonify({"contacts": []})
    contacts = db.search_contacts(query)
    return jsonify({"contacts": contacts})


@app.route("/api/emails/<int:email_id>/important", methods=["POST"])
def toggle_important(email_id):
    """Mark/unmark an email as important."""
    data = request.json or {}
    is_important = data.get("is_important", True)
    db.mark_important(email_id, is_important)
    action = "marked important" if is_important else "unmarked as important"
    email = db.get_email_by_id(email_id)
    if email:
        db.log_event("manual_important", f"Email {action}: {email.get('subject', '')}", {"email_id": email_id})
    return jsonify({"success": True, "is_important": is_important})


# ============================================================
# Sync API
# ============================================================

@app.route("/api/sync", methods=["POST"])
def sync_emails():
    """Sync emails from all accounts (or a specific one)."""
    global sync_status

    if sync_status["is_syncing"]:
        return jsonify({"success": False, "message": "Sync already in progress"}), 409

    target_account = request.json.get("account") if request.json else None
    accounts = auth_manager.list_accounts()

    if target_account:
        accounts = [a for a in accounts if a["email"] == target_account]

    if not accounts:
        return jsonify({"success": False, "message": "No accounts to sync"}), 400

    thread = threading.Thread(target=_do_sync_for_accounts, args=(accounts,), daemon=True)
    thread.start()

    return jsonify({"success": True, "message": "Sync started"})


@app.route("/api/sync/auto", methods=["POST"])
def control_auto_sync():
    """Enable or disable automatic periodic sync."""
    global _auto_sync_enabled, _sync_thread

    data = request.json or {}
    enabled = data.get("enabled", False)
    interval = data.get("interval", 10)

    if enabled and not _auto_sync_enabled:
        _auto_sync_enabled = True
        _auto_sync_interval = interval
        _sync_thread = threading.Thread(target=_auto_sync_thread, daemon=True)
        _sync_thread.start()
        return jsonify({"success": True, "message": f"Auto-sync enabled (interval: {interval}s)"})

    elif not enabled and _auto_sync_enabled:
        _auto_sync_enabled = False
        return jsonify({"success": True, "message": "Auto-sync disabled"})

    elif enabled and _auto_sync_enabled:
        _auto_sync_interval = interval
        return jsonify({"success": True, "message": f"Auto-sync updated (interval: {interval}s)"})

    else:
        return jsonify({"success": False, "message": "Auto-sync already disabled"}), 400


@app.route("/api/sync/auto/status", methods=["GET"])
def get_auto_sync_status():
    """Get auto-sync status."""
    return jsonify({
        "auto_sync_enabled": _auto_sync_enabled,
        "interval": _auto_sync_interval,
        "current_sync": sync_status,
    })


@app.route("/api/sync/status", methods=["GET"])
def get_sync_status():
    """Get the current sync progress."""
    return jsonify(sync_status)


# ============================================================
# Settings API
# ============================================================

@app.route("/api/settings", methods=["GET"])
def get_settings():
    """Get all settings."""
    persona = db.get_setting("agent_persona", "")
    settings = get_ai_settings()
    settings["agent_persona"] = persona
    return jsonify({"settings": settings})


@app.route("/api/settings", methods=["POST"])
def update_settings():
    """Update settings."""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    if "agent_persona" in data:
        db.set_setting("agent_persona", data["agent_persona"])

    for key in AI_SETTING_KEYS:
        if key in data:
            value = data[key]
            if key == "ai_provider":
                if value not in {"local", "cloud"}:
                    return jsonify({"success": False, "error": "Invalid AI provider. Must be 'local' or 'cloud'"}), 400
                print(f"[Settings] Switching to {value} model")
                db.log_event("model_switch", f"Switched AI provider to {value}", {"provider": value})
            elif key == "cloud_provider":
                if value not in {"nim", "gemini", "", None}:
                    return jsonify({"success": False, "error": "Only Nvidia NIM is supported"}), 400
            elif key == "force_provider":
                value = "true" if value else "false"

            db.set_setting(key, str(value or ""))

    return jsonify({"success": True})


@app.route("/api/models/test", methods=["POST"])
def test_model_provider():
    """Test the selected AI provider connection."""
    data = request.json or {}
    settings = get_ai_settings()
    settings.update({key: data[key] for key in AI_SETTING_KEYS if key in data})
    result = ai_engine.test_provider(settings)
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@app.route("/api/models/test-local", methods=["POST"])
def test_local_model():
    """Test the local LM Studio model specifically."""
    data = request.json or {}
    settings = get_ai_settings()
    if "local_base_url" in data:
        settings["local_base_url"] = data["local_base_url"]
    if "local_model" in data:
        settings["local_model"] = data["local_model"]
    result = ai_engine.test_specific_provider("local", settings)
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@app.route("/api/models/test-cloud", methods=["POST"])
def test_cloud_model():
    """Test the cloud Gemini model specifically."""
    data = request.json or {}
    settings = get_ai_settings()
    if "cloud_model" in data:
        settings["cloud_model"] = data["cloud_model"]
    result = ai_engine.test_specific_provider("cloud", settings)
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@app.route("/api/models/test-lmstudio", methods=["POST"])
def test_lmstudio_direct():
    """Test LM Studio connection directly with debug output."""
    data = request.json or {}
    base_url = data.get("url", config.LMSTUDIO_BASE_URL)
    model_name = data.get("model", config.LMSTUDIO_MODEL)

    print(f"[Test] Testing LM Studio directly: {base_url}/{model_name}")

    try:
        import requests as req

        if base_url.rstrip('/').endswith("/v1"):
            models_endpoint = f"{base_url.rstrip('/')}/models"
        else:
            models_endpoint = f"{base_url.rstrip('/')}/v1/models"

        response = req.get(models_endpoint, timeout=5)
        if response.status_code == 200:
            models = response.json().get("data", [])
            actual_model = models[0]["id"] if models else model_name
        else:
            return jsonify({"success": False, "error": f"Models endpoint error: {response.status_code}"}), 400

        test_prompt = "Hello, test the connection."

        if base_url.rstrip('/').endswith("/v1"):
            completions_endpoint = f"{base_url.rstrip('/')}/chat/completions"
        else:
            completions_endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"

        response = req.post(
            completions_endpoint,
            json={
                "model": actual_model,
                "messages": [{"role": "user", "content": test_prompt}],
                "temperature": 0.2,
                "max_tokens": 50,
            },
            timeout=10
        )

        try:
            rdata = response.json()
            content = rdata["choices"][0]["message"]["content"]
            return jsonify({
                "success": True,
                "model": actual_model,
                "url": base_url,
                "response": content[:200] + "...",
                "full_response_available": True
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        print(f"[Test] Error testing LM Studio: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/models/status", methods=["GET"])
def get_model_status():
    """Get current model configuration and health status."""
    settings = get_ai_settings()
    provider = settings.get("ai_provider", "unknown")

    if provider == "local":
        model_name = settings.get("local_model", "(auto-detect)")
        config_url = settings.get("local_base_url", "unknown")
    else:
        model_name = settings.get("cloud_model", "unknown")
        config_url = "-"

    test_result = ai_engine.test_provider(settings)

    return jsonify({
        "current_provider": provider,
        "model_name": model_name,
        "config_url": config_url,
        "is_healthy": test_result.get("success", False),
        "health_message": test_result.get("message") or test_result.get("error", "Unknown"),
        "available_providers": ai_engine.get_available_providers(settings),
        "force_provider": settings.get("force_provider", False),
    })


# ============================================================
# Email Compose API
# ============================================================

@app.route("/api/emails/rewrite", methods=["POST"])
def rewrite_email():
    """Rewrite email text to be professional using AI."""
    data = request.json
    if not data or not data.get("text"):
        return jsonify({"success": False, "error": "No text provided"}), 400

    try:
        persona = db.get_setting("agent_persona", "")
        rewritten_text = ai_engine.rewrite_email(
            data.get("text"),
            persona=persona,
            settings=get_ai_settings(),
        )
        return jsonify({"success": True, "text": rewritten_text})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/emails/compose", methods=["POST"])
def compose_email():
    """Compose an email from a natural language instruction."""
    data = request.json or {}
    instruction = data.get("instruction", "").strip()
    if not instruction:
        return jsonify({"success": False, "error": "No instruction provided"}), 400

    try:
        persona = db.get_setting("agent_persona", "")
        result = ai_engine.compose_email(
            instruction=instruction,
            persona=persona,
            settings=get_ai_settings(),
        )
        return jsonify({"success": True, **result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/emails/send", methods=["POST"])
def send_email():
    """Send an email from a connected account."""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    from_email = data.get("from")
    to_email = data.get("to")
    subject = data.get("subject", "")
    body = data.get("body", "")

    if not from_email or not to_email:
        return jsonify({"success": False, "error": "Missing 'from' or 'to' field"}), 400

    result = gmail_client.send_email(from_email, to_email, subject, body)
    if result.get("success"):
        db.log_event("email_sent", f"Email sent to {to_email}",
                     {"from": from_email, "to": to_email, "subject": subject})
    return jsonify(result)


@app.route("/api/emails/schedule", methods=["POST"])
def schedule_email():
    """Schedule an email to be sent at a specific time."""
    data = request.json or {}
    from_email = data.get("from")
    to_email = data.get("to")
    subject = data.get("subject", "")
    body = data.get("body", "")
    send_at = data.get("send_at", "")
    schedule_hint = data.get("schedule_hint", "")

    if not from_email or not to_email:
        return jsonify({"success": False, "error": "Missing 'from' or 'to' field"}), 400

    # Parse natural language time if needed
    if not send_at and schedule_hint:
        try:
            send_at = ai_engine.parse_schedule_time(schedule_hint, settings=get_ai_settings())
        except Exception as e:
            return jsonify({"success": False, "error": f"Could not parse schedule time: {str(e)}"}), 400

    if not send_at:
        return jsonify({"success": False, "error": "No send_at time provided"}), 400

    scheduled_id = db.create_scheduled_email(from_email, to_email, subject, body, send_at)
    db.log_event("email_scheduled", f"Email scheduled to {to_email} at {send_at}",
                 {"from": from_email, "to": to_email, "subject": subject, "send_at": send_at})
    return jsonify({"success": True, "scheduled_id": scheduled_id, "send_at": send_at})


@app.route("/api/emails/scheduled", methods=["GET"])
def get_scheduled_emails():
    """Get all scheduled emails."""
    status = request.args.get("status")
    scheduled = db.get_scheduled_emails(status=status)
    return jsonify({"scheduled": scheduled, "count": len(scheduled)})


@app.route("/api/emails/scheduled/<int:scheduled_id>", methods=["DELETE"])
def delete_scheduled_email(scheduled_id):
    """Cancel/delete a scheduled email."""
    db.delete_scheduled_email(scheduled_id)
    return jsonify({"success": True})


# ============================================================
# Agent Rules API
# ============================================================

@app.route("/api/agent/rules", methods=["GET"])
def get_rules():
    """Get all agent auto-reply rules."""
    active_only = request.args.get("active_only", "false").lower() == "true"
    rules = db.get_rules(active_only=active_only)
    return jsonify({"rules": rules, "count": len(rules)})


@app.route("/api/agent/rules", methods=["POST"])
def create_rule():
    """Create a new auto-reply rule."""
    data = request.json or {}
    name = data.get("name", "").strip()
    trigger_keywords = data.get("trigger_keywords", [])
    reply_template = data.get("reply_template", "").strip()
    time_condition = data.get("time_condition", "")
    account = data.get("account", "")

    if not name or not trigger_keywords or not reply_template:
        return jsonify({"success": False, "error": "name, trigger_keywords, and reply_template are required"}), 400

    rule_id = db.create_rule(name, trigger_keywords, reply_template, time_condition, account)
    db.log_event("rule_created", f"Auto-reply rule created: {name}", {"rule_id": rule_id, "name": name})
    return jsonify({"success": True, "rule_id": rule_id})


@app.route("/api/agent/rules/<int:rule_id>", methods=["PUT"])
def update_rule(rule_id):
    """Update an auto-reply rule."""
    data = request.json or {}
    allowed = {"name", "trigger_keywords", "reply_template", "time_condition", "account", "is_active"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if updates:
        db.update_rule(rule_id, **updates)
    return jsonify({"success": True})


@app.route("/api/agent/rules/<int:rule_id>", methods=["DELETE"])
def delete_rule(rule_id):
    """Delete an auto-reply rule."""
    db.delete_rule(rule_id)
    db.log_event("rule_deleted", f"Auto-reply rule deleted (id={rule_id})", {"rule_id": rule_id})
    return jsonify({"success": True})


# ============================================================
# Activity Logs API
# ============================================================

@app.route("/api/logs", methods=["GET"])
def get_logs():
    """Get activity log entries."""
    event_type = request.args.get("event_type")
    limit = int(request.args.get("limit", 100))
    logs = db.get_logs(event_type=event_type, limit=limit)
    return jsonify({"logs": logs, "count": len(logs)})


# ============================================================
# Dashboard & Stats API
# ============================================================

@app.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    """Get dashboard overview with categorized emails."""
    account = request.args.get("account")
    limit = int(request.args.get("limit", 50))

    emails = db.get_emails(account=account, limit=limit, offset=0)

    dashboard = {
        "critical": [],
        "important": [],
        "normal": [],
        "low": [],
        "categories": {}
    }

    for email in emails:
        priority_score = email.get("priority_score", 3)
        if priority_score >= 5:
            priority_label = "critical"
        elif priority_score == 4:
            priority_label = "important"
        elif priority_score == 3:
            priority_label = "normal"
        else:
            priority_label = "low"

        if priority_label in dashboard:
            dashboard[priority_label].append({
                "id": email["id"],
                "subject": email.get("subject", ""),
                "sender": email.get("sender", ""),
                "date": email.get("date", ""),
                "category": email.get("category", "other"),
                "priority_score": priority_score,
                "short_summary": email.get("short_summary", "") or email.get("summary", "")[:120],
                "summary": email.get("summary", ""),
                "is_read": bool(email.get("is_read", False)),
                "is_important": bool(email.get("is_important", False)),
                "account": email.get("account", ""),
            })

        cat = email.get("category", "other")
        if cat not in dashboard["categories"]:
            dashboard["categories"][cat] = []
        dashboard["categories"][cat].append({
            "id": email["id"],
            "subject": email.get("subject", ""),
            "sender": email.get("sender", ""),
            "priority_score": priority_score,
        })

    stats = db.get_stats(account)

    return jsonify({
        "dashboard": dashboard,
        "stats": stats,
        "total_emails": len(emails)
    })


@app.route("/api/overview", methods=["GET"])
def get_overview():
    """Return a compact dashboard overview."""
    account = request.args.get("account")
    stats = db.get_stats(account)
    emails = db.get_emails(account=account, limit=24)
    tasks = []
    for email in emails[:6]:
        tasks.append({
            "email_id": email["id"],
            "subject": email.get("subject", ""),
            "priority": email.get("priority", "normal"),
            "category": email.get("category", "other"),
            "short_summary": email.get("short_summary", "") or email.get("summary", "")[:100],
            "summary": email.get("summary", ""),
            "sender": email.get("sender", ""),
            "is_important": bool(email.get("is_important", False)),
        })
    return jsonify({
        "stats": stats,
        "emails": emails,
        "top_tasks": tasks,
    })


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get dashboard statistics."""
    account = request.args.get("account")
    stats = db.get_stats(account)
    return jsonify(stats)


# ============================================================
# Agent API
# ============================================================

@app.route("/api/agent/tasks", methods=["POST"])
def suggest_mail_tasks():
    """Suggest follow-up tasks for a mail context."""
    data = request.json or {}
    scope = data.get("scope", "all")
    account = data.get("account")
    email_id = data.get("email_id")
    limit = int(data.get("limit", 12))
    emails = _fetch_scope_emails(scope=scope, account=account, email_id=email_id, limit=limit)

    if not emails:
        return jsonify({"success": False, "error": "No email context found"}), 404

    first = emails[0]
    result = ai_engine.suggest_tasks(
        subject=first.get("subject", ""),
        body=first.get("body", ""),
        sender=first.get("sender", ""),
        settings=get_ai_settings(),
    )
    result["context"] = emails
    result["scope"] = scope
    result["account"] = account
    result["email_id"] = email_id
    return jsonify({"success": True, "result": result})


@app.route("/api/agent/tasks", methods=["GET"])
def get_agent_tasks():
    """Get all pending agent tasks."""
    email_id = request.args.get("email_id", type=int)
    status = request.args.get("status", "pending")
    tasks = db.get_tasks(email_id=email_id, status=status)
    return jsonify({"tasks": tasks})


@app.route("/api/agent/task/<int:task_id>/complete", methods=["POST"])
def complete_task(task_id):
    """Mark a task as completed."""
    db.update_task_status(task_id, "completed")
    return jsonify({"success": True, "message": "Task completed"})


@app.route("/api/agent/analyze/<int:email_id>", methods=["GET"])
def analyze_email(email_id):
    """Analyze an email and generate task suggestions."""
    email = db.get_email_by_id(email_id)
    if not email:
        return jsonify({"error": "Email not found"}), 404

    tasks = agent.analyze_email_for_tasks(email, settings=get_ai_settings())
    action = agent.smart_categorize_email(email)

    task_ids = []
    for task in tasks:
        task_id = db.create_task(
            email_id=email_id,
            task_type=task["type"],
            title=task["title"],
            description=task["description"],
            priority=task.get("priority", "normal")
        )
        task_ids.append(task_id)

    return jsonify({
        "email_id": email_id,
        "subject": email["subject"],
        "suggested_tasks": tasks,
        "action_suggestion": action,
        "task_ids": task_ids
    })


@app.route("/api/agent/draft-reply/<int:email_id>", methods=["GET"])
def generate_draft_reply(email_id):
    """Generate a draft reply for an email."""
    scope = request.args.get("scope", "professional")

    email = db.get_email_by_id(email_id)
    if not email:
        return jsonify({"error": "Email not found"}), 404

    draft = agent.generate_draft_reply(email, scope=scope, settings=get_ai_settings())

    if draft["success"]:
        suggestion_id = db.create_suggestion(
            email_id=email_id,
            suggestion_type="draft_reply",
            text=f"Draft reply generated for {email['subject']}",
            draft=draft["draft_body"],
            scope=scope
        )
        draft["suggestion_id"] = suggestion_id

    return jsonify(draft)


@app.route("/api/agent/suggestions/<int:email_id>", methods=["GET"])
def get_suggestions(email_id):
    """Get suggestions for an email."""
    suggestions = db.get_suggestions(email_id)
    return jsonify({"suggestions": suggestions})


@app.route("/api/agent/suggestion/<int:suggestion_id>/accept", methods=["POST"])
def accept_suggestion(suggestion_id):
    """Accept/use a suggestion."""
    db.accept_suggestion(suggestion_id)
    return jsonify({"success": True, "message": "Suggestion accepted"})


def detect_topic_search(message: str) -> str | None:
    """Detect if query is of type 'emails related to <something>' and extract topic."""
    import re
    cleaned = message.strip().strip("'\"").strip()
    match = re.search(r'(?:emails?|mails?)\s+related\s+to\s+([a-zA-Z0-9\s_\-]+)', cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'related\s+to\s+([a-zA-Z0-9\s_\-]+)\s+(?:emails?|mails?)', cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


@app.route("/api/chat", methods=["POST"])
def chat_mail():
    """Chat with the mail corpus using a selectable scope."""
    data = request.json or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"success": False, "error": "No message provided"}), 400

    scope = data.get("scope", "all")
    account = data.get("account")
    email_id = data.get("email_id")
    session_id = data.get("session_id", str(uuid.uuid4()))
    limit = int(data.get("limit", 50))  # increased from 12 to fetch more emails
    
    settings = get_ai_settings()
    
    # ─── New Interceptor Logic ───
    if message.startswith("/info_email "):
        email_part = message.replace("/info_email ", "").strip()
        email_id_str = email_part.split("|")[0]
        try:
            email_id = int(email_id_str)
            email_info = db.get_email_by_id(email_id)
            if email_info:
                reply = ai_engine.chat_about_mail(
                    "Summarize what this email is about.",
                    context_emails=[email_info],
                    settings=settings,
                    scope_label=scope,
                    history=[]
                )
                db.add_chat_message(session_id, message, reply, scope=scope)
                return jsonify({
                    "success": True,
                    "reply": reply,
                    "scope": scope,
                    "session_id": session_id,
                    "email_count": 1,
                    "email_links": [{"id": email_info["id"], "subject": email_info.get("subject", "Email")}],
                })
        except Exception as e:
            pass

    topic = detect_topic_search(message)
    if topic:
        matching_emails = db.get_emails(search=topic, limit=20)
        if len(matching_emails) > 1:
            reply = f"I found several emails related to '{topic}'. Which one would you like to know more about?"
            options = [
                {
                    "label": f"Email #{e['id']}: {e.get('subject', 'No Subject')}",
                    "action": f"/info_email {e['id']}|{e.get('subject', 'No Subject')}"
                }
                for e in matching_emails[:5]
            ]
            db.add_chat_message(session_id, message, reply, scope=scope)
            return jsonify({
                "success": True,
                "reply": reply,
                "options": options,
                "scope": scope,
                "session_id": session_id,
                "email_count": len(matching_emails),
            })
        elif len(matching_emails) == 1:
            single_email = matching_emails[0]
            reply = ai_engine.chat_about_mail(
                "Summarize what this email is about.",
                context_emails=[single_email],
                settings=settings,
                scope_label=scope,
                history=[]
            )
            db.add_chat_message(session_id, message, reply, scope=scope)
            return jsonify({
                "success": True,
                "reply": reply,
                "scope": scope,
                "session_id": session_id,
                "email_count": 1,
                "email_links": [{"id": single_email["id"], "subject": single_email.get("subject", "Email")}],
            })
        else:
            reply = f"I couldn't find any emails related to '{topic}'."
            db.add_chat_message(session_id, message, reply, scope=scope)
            return jsonify({
                "success": True,
                "reply": reply,
                "scope": scope,
                "session_id": session_id,
                "email_count": 0,
            })

    # Fallback: search broadly across ALL emails (not just recent)
    # First try keyword search using message content
    import re
    keywords = re.findall(r'\b[a-zA-Z]{3,}\b', message)
    context_emails = []
    
    # Try keyword search first to find relevant old emails
    if keywords:
        search_term = ' '.join(keywords[:3])
        context_emails = db.get_emails(account=account or None, search=search_term, limit=30)
    
    # If no keyword match, fall back to recent emails (broad context)
    if not context_emails:
        context_emails = _fetch_scope_emails(scope=scope, account=account, email_id=email_id, limit=50)
    
    # If still nothing, let AI answer generically
    if not context_emails:
        history = db.get_chat_history(session_id, limit=10) if session_id else []
        reply = ai_engine.chat_about_mail(
            message,
            context_emails=[],
            settings=settings,
            scope_label=scope,
            history=history,
        ) if hasattr(ai_engine, 'chat_about_mail') else "\ud83d\udce2 I don't have any emails in my database yet. Please sync your emails first by clicking the Sync button!"
        db.add_chat_message(session_id, message, reply, scope=scope)
        return jsonify({"success": True, "reply": reply, "scope": scope, "session_id": session_id, "email_count": 0, "email_links": []})

    # Get chat history for context
    history = db.get_chat_history(session_id, limit=10) if session_id else []

    reply = ai_engine.chat_about_mail(
        message,
        context_emails=context_emails,
        settings=settings,
        scope_label=scope,
        history=history,
    )

    db.add_chat_message(session_id, message, reply, scope=scope)

    # If user asked about a single specific email, attach an open link
    email_links = []
    if email_id and len(context_emails) == 1:
        email_links = [{"id": context_emails[0]["id"], "subject": context_emails[0].get("subject", "Email")}]

    return jsonify({
        "success": True,
        "reply": reply,
        "scope": scope,
        "session_id": session_id,
        "email_count": len(context_emails),
        "email_links": email_links,
    })


@app.route("/api/chat/send", methods=["POST"])
def send_chat_message():
    """Send a message to the email chat assistant."""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    user_message = data.get("message", "")
    email_id = data.get("email_id")
    scope = data.get("scope", "professional")
    session_id = data.get("session_id", str(uuid.uuid4()))
    account = data.get("account")

    if not user_message:
        return jsonify({"success": False, "error": "Message is required"}), 400

    # 1. Check for /info_email slash command
    if user_message.startswith("/info_email "):
        email_part = user_message.replace("/info_email ", "").strip()
        email_id_str = email_part.split("|")[0]
        try:
            email_id = int(email_id_str)
            email_info = db.get_email_by_id(email_id)
            if email_info:
                response = agent.generate_chat_response(
                    "Summarize what this email is about.",
                    email=email_info,
                    scope=scope,
                    settings=get_ai_settings(),
                    history=[]
                )
                agent_res_text = response.get("response") if isinstance(response, dict) else response
                db.add_chat_message(session_id, user_message, agent_res_text, email_id=email_id, scope=scope)
                return jsonify({
                    "success": True,
                    "session_id": session_id,
                    "user_message": user_message,
                    "agent_response": agent_res_text,
                    "scope": scope,
                    "options": []
                })
        except Exception as e:
            pass

    # 2. Check for topic-based search
    topic = detect_topic_search(user_message)
    if topic:
        matching_emails = db.get_emails(search=topic, limit=20)
        if len(matching_emails) > 1:
            reply = f"I found several emails related to '{topic}'. Which one would you like to know more about?"
            options = [
                {
                    "label": f"Email #{e['id']}: {e.get('subject', 'No Subject')}",
                    "action": f"/info_email {e['id']}|{e.get('subject', 'No Subject')}"
                }
                for e in matching_emails[:5]
            ]
            db.add_chat_message(session_id, user_message, reply, scope=scope)
            return jsonify({
                "success": True,
                "session_id": session_id,
                "user_message": user_message,
                "agent_response": reply,
                "scope": scope,
                "options": options
            })
        elif len(matching_emails) == 1:
            single_email = matching_emails[0]
            response = agent.generate_chat_response(
                "Summarize what this email is about.",
                email=single_email,
                scope=scope,
                settings=get_ai_settings(),
                history=[]
            )
            agent_res_text = response.get("response") if isinstance(response, dict) else response
            db.add_chat_message(session_id, user_message, agent_res_text, email_id=single_email["id"], scope=scope)
            return jsonify({
                "success": True,
                "session_id": session_id,
                "user_message": user_message,
                "agent_response": agent_res_text,
                "scope": scope,
                "options": []
            })
        else:
            reply = f"I couldn't find any emails related to '{topic}'."
            db.add_chat_message(session_id, user_message, reply, scope=scope)
            return jsonify({
                "success": True,
                "session_id": session_id,
                "user_message": user_message,
                "agent_response": reply,
                "scope": scope,
                "options": []
            })

    # 3. Fallback to default chat behavior
    email = None
    if email_id:
        email = db.get_email_by_id(email_id)

    # Get history for multi-turn context
    history = db.get_chat_history(session_id, limit=10)

    response = agent.generate_chat_response(
        user_message,
        email=email,
        scope=scope,
        settings=get_ai_settings(),
        history=history,
    )

    agent_res_text = response.get("response") if isinstance(response, dict) else response
    options = response.get("options") if isinstance(response, dict) else []

    db.add_chat_message(session_id, user_message, agent_res_text, email_id=email_id, scope=scope)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "user_message": user_message,
        "agent_response": agent_res_text,
        "scope": scope,
        "options": options
    })


@app.route("/api/chat/history", methods=["GET"])
def get_chat_history():
    """Get chat history for a session."""
    session_id = request.args.get("session_id")
    email_id = request.args.get("email_id", type=int)
    limit = request.args.get("limit", 50, type=int)

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    history = db.get_chat_history(session_id, email_id=email_id, limit=limit)
    return jsonify({"history": history, "session_id": session_id})


@app.route("/api/chat/sessions", methods=["GET"])
def get_chat_sessions():
    """Get list of all chat sessions with their first message as title."""
    try:
        conn = db._get_conn()
        rows = conn.execute("""
            SELECT session_id,
                   MIN(created_at) as created_at,
                   MAX(created_at) as last_message_at,
                   COUNT(*) as message_count,
                   (SELECT user_message FROM chat_history h2
                    WHERE h2.session_id = chat_history.session_id
                      AND user_message NOT LIKE '/%'
                    ORDER BY created_at ASC LIMIT 1) as first_message,
                   (SELECT user_message FROM chat_history h3
                    WHERE h3.session_id = chat_history.session_id
                    ORDER BY created_at ASC LIMIT 1) as any_message
            FROM chat_history
            GROUP BY session_id
            ORDER BY last_message_at DESC
            LIMIT 50
        """).fetchall()
        conn.close()
        sessions = []
        for row in rows:
            d = dict(row)
            # Use non-slash first message as title, fall back to any message
            raw_title = d.get("first_message") or d.get("any_message") or "New Chat"
            # Strip slash commands from display
            if raw_title.startswith("/info_email "):
                parts = raw_title.replace("/info_email ", "").split("|")
                raw_title = f"📧 Email: {parts[1]}" if len(parts) > 1 else f"Email #{parts[0]}"
            elif raw_title.startswith("/summarize_contact "):
                raw_title = f"📋 {raw_title.replace('/summarize_contact ', '')}"
            # Truncate to 40 chars
            title = raw_title[:37] + "..." if len(raw_title) > 40 else raw_title
            sessions.append({
                "session_id": d["session_id"],
                "title": title,
                "created_at": d["created_at"],
                "last_message_at": d["last_message_at"],
                "message_count": d["message_count"],
            })
        return jsonify({"sessions": sessions})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"sessions": [], "error": str(e)})


# ============================================================
# Run
# ============================================================


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Gmail Agent Dashboard")
    print("  http://127.0.0.1:5000")
    print("=" * 60)

    accounts = auth_manager.list_accounts()
    if accounts:
        print(f"\n  Connected accounts: {len(accounts)}")
        for acc in accounts:
            print(f"    • {acc['email']}")
    else:
        print("\n  No accounts connected yet.")
        print("  Click 'Add Account' in the dashboard to get started.")

    # Start background scheduler
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()

    # Start incoming email monitor
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()

    print("=" * 60 + "\n")
    app.run(debug=True, port=5000, use_reloader=False)
