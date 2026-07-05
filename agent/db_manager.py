"""
Database Manager — SQLite storage for emails, accounts, tasks, rules, scheduled emails, and logs.
"""

import sqlite3
import json
from datetime import datetime, timezone

import config


class DBManager:
    """SQLite database for storing processed emails and account info."""

    def __init__(self):
        self.db_path = config.DB_PATH
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                email TEXT PRIMARY KEY,
                display_name TEXT,
                added_at TEXT,
                last_synced TEXT,
                total_messages INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account TEXT NOT NULL,
                gmail_id TEXT NOT NULL,
                thread_id TEXT,
                subject TEXT,
                sender TEXT,
                sender_email TEXT,
                recipient TEXT,
                date TEXT,
                snippet TEXT,
                body TEXT,
                priority TEXT DEFAULT 'normal',
                priority_score INTEGER DEFAULT 3,
                category TEXT DEFAULT 'other',
                short_summary TEXT,
                summary TEXT,
                key_points TEXT,
                action_items TEXT,
                is_read INTEGER DEFAULT 0,
                is_important INTEGER DEFAULT 0,
                labels TEXT,
                internal_date TEXT,
                processed_at TEXT,
                UNIQUE(account, gmail_id),
                FOREIGN KEY (account) REFERENCES accounts(email)
            )
        """)

        # Add columns that may not exist in older DB
        for col, col_def in [
            ("priority_score", "INTEGER DEFAULT 3"),
            ("short_summary", "TEXT"),
            ("key_points", "TEXT"),
            ("action_items", "TEXT"),
            ("is_important", "INTEGER DEFAULT 0"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE emails ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # Column already exists

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_account ON emails(account)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_priority ON emails(priority)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_category ON emails(category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_important ON emails(is_important)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Agent Tasks Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                task_type TEXT,
                task_title TEXT,
                task_description TEXT,
                suggested_action TEXT,
                status TEXT DEFAULT 'pending',
                priority TEXT DEFAULT 'normal',
                created_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_email ON agent_tasks(email_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON agent_tasks(status)
        """)

        # Agent Suggestions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                suggestion_type TEXT,
                suggestion_text TEXT,
                draft_response TEXT,
                confidence REAL,
                scope TEXT DEFAULT 'professional',
                created_at TEXT,
                accepted INTEGER DEFAULT 0,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_suggestions_email ON agent_suggestions(email_id)
        """)

        # Chat History Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER,
                session_id TEXT,
                user_message TEXT,
                agent_response TEXT,
                context TEXT,
                scope TEXT DEFAULT 'professional',
                created_at TEXT,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_email ON chat_history(email_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id)
        """)

        # Scheduled Emails Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_email TEXT NOT NULL,
                to_email TEXT NOT NULL,
                subject TEXT,
                body TEXT,
                send_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                sent_at TEXT,
                error_message TEXT,
                created_at TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_status ON scheduled_emails(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_send_at ON scheduled_emails(send_at)
        """)

        # Agent Rules Table (auto-reply rules)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                trigger_keywords TEXT,
                reply_template TEXT,
                time_condition TEXT,
                account TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                last_triggered TEXT,
                trigger_count INTEGER DEFAULT 0
            )
        """)

        # Activity Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_event ON activity_logs(event_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_created ON activity_logs(created_at)
        """)

        conn.commit()
        conn.close()

    # --- Account Operations ---

    def add_account(self, email: str, display_name: str = ""):
        """Add or update an account record."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO accounts (email, display_name, added_at, is_active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(email) DO UPDATE SET
                display_name = excluded.display_name,
                is_active = 1
        """,
            (email, display_name or email, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    def get_accounts(self) -> list[dict]:
        """Get all active accounts."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM accounts WHERE is_active = 1 ORDER BY added_at"
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def remove_account(self, email: str):
        """Soft-delete an account."""
        conn = self._get_conn()
        conn.execute("UPDATE accounts SET is_active = 0 WHERE email = ?", (email,))
        conn.commit()
        conn.close()

    def update_last_synced(self, email: str):
        """Update the last synced timestamp for an account."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE accounts SET last_synced = ? WHERE email = ?",
            (datetime.now(timezone.utc).isoformat(), email),
        )
        conn.commit()
        conn.close()

    # --- Email Operations ---

    def save_email(self, account: str, email_data: dict, ai_result: dict = None):
        """Save or update an email with AI analysis results."""
        conn = self._get_conn()

        sender = email_data.get("sender", "")
        sender_email = sender
        if "<" in sender and ">" in sender:
            sender_email = sender.split("<")[1].split(">")[0]

        ai_result = ai_result or {}
        labels_json = json.dumps(email_data.get("labels", []))

        # Map priority string to score
        priority_str = ai_result.get("priority", "normal")
        priority_score_map = {"critical": 5, "important": 4, "normal": 3, "low": 2}
        priority_score = ai_result.get("priority_score") or priority_score_map.get(priority_str, 3)

        conn.execute(
            """
            INSERT INTO emails (
                account, gmail_id, thread_id, subject, sender, sender_email,
                recipient, date, snippet, body, priority, priority_score, category,
                short_summary, summary, key_points, action_items,
                is_read, is_important, labels, internal_date, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account, gmail_id) DO UPDATE SET
                subject = excluded.subject,
                snippet = excluded.snippet,
                is_read = excluded.is_read,
                labels = excluded.labels,
                priority = COALESCE(excluded.priority, priority),
                priority_score = COALESCE(excluded.priority_score, priority_score),
                category = COALESCE(excluded.category, category),
                short_summary = COALESCE(excluded.short_summary, short_summary),
                summary = COALESCE(excluded.summary, summary),
                key_points = COALESCE(excluded.key_points, key_points),
                action_items = COALESCE(excluded.action_items, action_items),
                is_important = COALESCE(excluded.is_important, is_important),
                processed_at = excluded.processed_at
        """,
            (
                account,
                email_data.get("id", ""),
                email_data.get("thread_id", ""),
                email_data.get("subject", ""),
                sender,
                sender_email,
                email_data.get("to", ""),
                email_data.get("date", ""),
                email_data.get("snippet", ""),
                email_data.get("body", ""),
                priority_str,
                priority_score,
                ai_result.get("category", "other"),
                ai_result.get("short_summary", ""),
                ai_result.get("summary", ""),
                json.dumps(ai_result.get("key_points", [])),
                json.dumps(ai_result.get("action_items", [])),
                1 if email_data.get("is_read", False) else 0,
                1 if ai_result.get("is_important", False) else 0,
                labels_json,
                email_data.get("internal_date", "0"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def get_emails(
        self,
        account: str = None,
        category: str = None,
        priority_score: int = None,
        is_read: bool = None,
        is_important: bool = None,
        search: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get emails with optional filters."""
        conn = self._get_conn()
        query = "SELECT * FROM emails WHERE 1=1"
        params = []

        if account:
            query += " AND account = ?"
            params.append(account)

        if category:
            query += " AND category = ?"
            params.append(category)

        if priority_score is not None:
            query += " AND priority_score = ?"
            params.append(priority_score)

        if is_read is not None:
            query += " AND is_read = ?"
            params.append(1 if is_read else 0)

        if is_important is not None:
            query += " AND is_important = ?"
            params.append(1 if is_important else 0)

        if search:
            query += " AND (subject LIKE ? OR sender LIKE ? OR summary LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])

        query += " ORDER BY internal_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_email_by_id(self, email_id: int) -> dict | None:
        """Get a single email by its database ID."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_email_by_gmail_id(self, account: str, gmail_id: str) -> dict | None:
        """Get a single email by Gmail message ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM emails WHERE account = ? AND gmail_id = ?",
            (account, gmail_id),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def email_exists(self, account: str, gmail_id: str) -> bool:
        """Check if an email already exists in the database."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM emails WHERE account = ? AND gmail_id = ?",
            (account, gmail_id),
        ).fetchone()
        conn.close()
        return row is not None

    def search_contacts(self, query: str) -> list[dict]:
        """Search for unique sender names and emails matching the query."""
        conn = self._get_conn()
        search_term = f"%{query}%"
        rows = conn.execute(
            "SELECT DISTINCT sender, sender_email FROM emails WHERE sender LIKE ? OR sender_email LIKE ? LIMIT 50",
            (search_term, search_term)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def mark_important(self, email_id: int, is_important: bool = True):
        """Mark or unmark an email as important."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE emails SET is_important = ? WHERE id = ?",
            (1 if is_important else 0, email_id)
        )
        conn.commit()
        conn.close()

    def get_stats(self, account: str = None) -> dict:
        """Get email statistics for the dashboard."""
        conn = self._get_conn()
        base = "FROM emails"
        params = []

        if account:
            base += " WHERE account = ?"
            params.append(account)

        total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        unread_q = base + (" AND" if account else " WHERE") + " is_read = 0"
        unread = conn.execute(f"SELECT COUNT(*) {unread_q}", params).fetchone()[0]
        important_q = base + (" AND" if account else " WHERE") + " is_important = 1"
        important = conn.execute(f"SELECT COUNT(*) {important_q}", params).fetchone()[0]

        priorities = {}
        score_ranges = {"critical": (5, 5), "important": (4, 4), "normal": (3, 3), "low": (1, 2)}
        for p, (lo, hi) in score_ranges.items():
            pq = base + (" AND" if account else " WHERE") + " priority_score BETWEEN ? AND ?"
            count = conn.execute(f"SELECT COUNT(*) {pq}", params + [lo, hi]).fetchone()[0]
            priorities[p] = count

        categories = {}
        for c in ["work", "personal", "finance", "newsletter", "social", "promotion", "security", "other"]:
            cq = base + (" AND" if account else " WHERE") + " category = ?"
            count = conn.execute(f"SELECT COUNT(*) {cq}", params + [c]).fetchone()[0]
            categories[c] = count

        account_counts = {}
        rows = conn.execute(
            "SELECT account, COUNT(*) as cnt FROM emails GROUP BY account"
        ).fetchall()
        for row in rows:
            account_counts[row["account"]] = row["cnt"]

        conn.close()

        return {
            "total": total,
            "unread": unread,
            "important": important,
            "priorities": priorities,
            "categories": categories,
            "account_counts": account_counts,
        }

    def mark_read(self, email_id: int):
        """Mark an email as read in the database."""
        conn = self._get_conn()
        conn.execute("UPDATE emails SET is_read = 1 WHERE id = ?", (email_id,))
        conn.commit()
        conn.close()

    # --- Settings Operations ---

    def get_setting(self, key: str, default: str = "") -> str:
        """Get a setting by key."""
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        conn.close()
        return dict(row)["value"] if row else default

    def set_setting(self, key: str, value: str):
        """Set a setting by key."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value)
        )
        conn.commit()
        conn.close()

    # --- Agent Tasks ---

    def create_task(self, email_id: int, task_type: str, title: str, description: str, priority: str = "normal") -> int:
        """Create a new agent task."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_tasks (email_id, task_type, task_title, task_description, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (email_id, task_type, title, description, priority, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        task_id = cursor.lastrowid
        conn.close()
        return task_id

    def get_tasks(self, email_id: int = None, status: str = None) -> list[dict]:
        """Get agent tasks with optional filters."""
        conn = self._get_conn()
        query = "SELECT * FROM agent_tasks WHERE 1=1"
        params = []

        if email_id:
            query += " AND email_id = ?"
            params.append(email_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_task_status(self, task_id: int, status: str):
        """Update task status."""
        conn = self._get_conn()
        completed_at = datetime.now(timezone.utc).isoformat() if status == "completed" else None
        conn.execute(
            "UPDATE agent_tasks SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed_at, task_id)
        )
        conn.commit()
        conn.close()

    # --- Agent Suggestions ---

    def create_suggestion(self, email_id: int, suggestion_type: str, text: str, draft: str = "", scope: str = "professional") -> int:
        """Create a suggestion for an email."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_suggestions (email_id, suggestion_type, suggestion_text, draft_response, scope, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (email_id, suggestion_type, text, draft, scope, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        suggestion_id = cursor.lastrowid
        conn.close()
        return suggestion_id

    def get_suggestions(self, email_id: int) -> list[dict]:
        """Get suggestions for an email."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM agent_suggestions WHERE email_id = ? ORDER BY created_at DESC",
            (email_id,)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def accept_suggestion(self, suggestion_id: int):
        """Mark a suggestion as accepted."""
        conn = self._get_conn()
        conn.execute("UPDATE agent_suggestions SET accepted = 1 WHERE id = ?", (suggestion_id,))
        conn.commit()
        conn.close()

    # --- Chat History ---

    def add_chat_message(self, session_id: str, user_msg: str, agent_response: str, email_id: int = None, scope: str = "professional"):
        """Store a chat message exchange."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO chat_history (email_id, session_id, user_message, agent_response, scope, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (email_id, session_id, user_msg, agent_response, scope, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()

    def get_chat_history(self, session_id: str, email_id: int = None, limit: int = 50) -> list[dict]:
        """Get chat history for a session."""
        conn = self._get_conn()
        query = "SELECT * FROM chat_history WHERE session_id = ?"
        params = [session_id]

        if email_id:
            query += " AND email_id = ?"
            params.append(email_id)

        query += f" ORDER BY created_at DESC LIMIT {limit}"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in reversed(rows)]

    # --- Scheduled Emails ---

    def create_scheduled_email(self, from_email: str, to_email: str, subject: str, body: str, send_at: str) -> int:
        """Schedule an email to be sent at a specific time."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO scheduled_emails (from_email, to_email, subject, body, send_at, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (from_email, to_email, subject, body, send_at, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        scheduled_id = cursor.lastrowid
        conn.close()
        return scheduled_id

    def get_scheduled_emails(self, status: str = None) -> list[dict]:
        """Get scheduled emails, optionally filtered by status."""
        conn = self._get_conn()
        query = "SELECT * FROM scheduled_emails WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY send_at ASC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_pending_scheduled_emails(self) -> list[dict]:
        """Get emails due to be sent now."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM scheduled_emails WHERE status = 'pending' AND send_at <= ?",
            (now,)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_scheduled_email_status(self, scheduled_id: int, status: str, error_message: str = None):
        """Update status of a scheduled email."""
        conn = self._get_conn()
        sent_at = datetime.now(timezone.utc).isoformat() if status == "sent" else None
        conn.execute(
            "UPDATE scheduled_emails SET status = ?, sent_at = ?, error_message = ? WHERE id = ?",
            (status, sent_at, error_message, scheduled_id)
        )
        conn.commit()
        conn.close()

    def delete_scheduled_email(self, scheduled_id: int):
        """Delete a scheduled email."""
        conn = self._get_conn()
        conn.execute("DELETE FROM scheduled_emails WHERE id = ?", (scheduled_id,))
        conn.commit()
        conn.close()

    # --- Agent Rules ---

    def create_rule(self, name: str, trigger_keywords: list, reply_template: str,
                    time_condition: str = "", account: str = "") -> int:
        """Create a new auto-reply rule."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_rules (name, trigger_keywords, reply_template, time_condition, account, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (name, json.dumps(trigger_keywords), reply_template, time_condition, account,
             datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        rule_id = cursor.lastrowid
        conn.close()
        return rule_id

    def get_rules(self, active_only: bool = True) -> list[dict]:
        """Get all auto-reply rules."""
        conn = self._get_conn()
        query = "SELECT * FROM agent_rules"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query).fetchall()
        conn.close()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d["trigger_keywords"] = json.loads(d.get("trigger_keywords", "[]"))
            except Exception:
                d["trigger_keywords"] = []
            result.append(d)
        return result

    def update_rule(self, rule_id: int, **kwargs):
        """Update a rule."""
        conn = self._get_conn()
        if "trigger_keywords" in kwargs and isinstance(kwargs["trigger_keywords"], list):
            kwargs["trigger_keywords"] = json.dumps(kwargs["trigger_keywords"])
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [rule_id]
        conn.execute(f"UPDATE agent_rules SET {sets} WHERE id = ?", vals)
        conn.commit()
        conn.close()

    def delete_rule(self, rule_id: int):
        """Delete a rule."""
        conn = self._get_conn()
        conn.execute("DELETE FROM agent_rules WHERE id = ?", (rule_id,))
        conn.commit()
        conn.close()

    def record_rule_trigger(self, rule_id: int):
        """Record that a rule was triggered."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE agent_rules SET trigger_count = trigger_count + 1, last_triggered = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), rule_id)
        )
        conn.commit()
        conn.close()

    # --- Activity Logs ---

    def log_event(self, event_type: str, description: str, details: dict = None):
        """Log an agent activity event."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO activity_logs (event_type, description, details, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (event_type, description, json.dumps(details or {}), datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()

    def get_logs(self, event_type: str = None, limit: int = 100) -> list[dict]:
        """Get activity log entries."""
        conn = self._get_conn()
        query = "SELECT * FROM activity_logs WHERE 1=1"
        params = []
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d["details"] = json.loads(d.get("details", "{}"))
            except Exception:
                d["details"] = {}
            result.append(d)
        return result