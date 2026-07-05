"""
AI Engine for email analysis, task drafting, and scoped chat.
Supports LM Studio local models and Gemini cloud models.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

import google.generativeai as genai
import requests

import config


class AIEngine:
    VALID_PRIORITIES = {"critical", "important", "normal", "low"}
    VALID_CATEGORIES = {
        "work", "personal", "finance", "newsletter",
        "social", "promotion", "security", "other",
    }

    PRIORITY_SCORE_MAP = {
        "critical": 5,
        "important": 4,
        "normal": 3,
        "low": 2,
    }

    def __init__(self):
        self._gemini_model_name = ""
        self._gemini_model = None
        self._request_count = 0
        self._last_request_time = 0.0

    def resolve_settings(self, settings: dict | None = None) -> dict:
        settings = settings or {}
        provider = (settings.get("ai_provider") or "").strip().lower()
        if provider not in {"local", "cloud"}:
            provider = "local" if self._local_available(settings) else "cloud"
        return {
            "ai_provider": provider,
            "local_base_url": settings.get("local_base_url") or config.LMSTUDIO_BASE_URL,
            "local_model": settings.get("local_model") or config.LMSTUDIO_MODEL,
            "cloud_provider": "gemini",
            "cloud_model": settings.get("cloud_model") or config.GEMINI_MODEL,
            "force_provider": bool(settings.get("force_provider", False)),
        }

    def get_available_providers(self, settings: dict | None = None) -> dict:
        resolved = self.resolve_settings(settings)
        return {
            "local": self._local_available(resolved),
            "cloud": bool(config.GEMINI_API_KEY),
        }

    def process_email(
        self,
        subject: str,
        body: str,
        sender: str = "",
        settings: dict | None = None,
    ) -> dict:
        prompt = f"""Analyze this email and return JSON only.

Subject: {subject}
From: {sender}
Body:
{(body or '')[:3500]}

Return ONLY valid JSON with these exact fields:
{{
  "priority": "critical|important|normal|low",
  "category": "work|personal|finance|newsletter|social|promotion|security|other",
  "short_summary": "One sentence (max 20 words) overview of what this email is about",
  "summary": "2-3 sentence detailed summary",
  "action_items": ["short task", "..."],
  "key_points": ["important fact", "..."],
  "is_important": true|false
}}"""

        raw = self._call_model(prompt, settings=settings, retries=2, max_tokens=700)
        if not raw:
            return self._fallback_analysis(subject)
        result = self._parse_json_response(raw, self._fallback_analysis(subject))

        # Ensure priority_score is set from priority string
        priority = result.get("priority", "normal")
        result["priority_score"] = self.PRIORITY_SCORE_MAP.get(priority, 3)

        return result

    def suggest_tasks(
        self,
        subject: str,
        body: str,
        sender: str = "",
        settings: dict | None = None,
    ) -> dict:
        prompt = f"""You are an autonomous email task assistant. Read the email and suggest what to do next.

Subject: {subject}
From: {sender}
Body:
{(body or '')[:3500]}

Return JSON only:
{{
  "task_type": "reply|follow_up|schedule|review|no_action",
  "priority": "critical|important|normal|low",
  "summary": "short summary",
  "suggested_reply": "draft reply text if relevant",
  "task_steps": ["step 1", "step 2"],
  "deadline_hint": "if any deadline is implied, otherwise empty string"
}}"""

        raw = self._call_model(prompt, settings=settings, retries=2, max_tokens=800)
        if not raw:
            return {
                "task_type": "no_action",
                "priority": "normal",
                "summary": subject or "No task suggested.",
                "suggested_reply": "",
                "task_steps": [],
                "deadline_hint": "",
            }
        data = self._parse_json_response(raw, {
            "task_type": "no_action",
            "priority": "normal",
            "summary": subject or "No task suggested.",
            "suggested_reply": "",
            "task_steps": [],
            "deadline_hint": "",
        })
        data.setdefault("task_type", "no_action")
        data.setdefault("suggested_reply", "")
        data.setdefault("task_steps", [])
        data.setdefault("deadline_hint", "")
        return data

    def rewrite_email(self, text: str, persona: str = "", settings: dict | None = None) -> str:
        if not text.strip():
            return ""
        persona_context = ""
        if persona.strip():
            persona_context = f"\nPersona:\n{persona}\n"
        prompt = f"""Rewrite this email draft to be clear, professional, and polite.
Keep the intent and important facts. Avoid sounding robotic.
{persona_context}
Draft:
{text}

Return only the final rewritten email."""
        raw = self._call_model(prompt, settings=settings, retries=2, max_tokens=500)
        return raw.strip() if raw else text

    def compose_email(
        self,
        instruction: str,
        persona: str = "",
        settings: dict | None = None,
    ) -> dict:
        """Compose a proper email from a natural language instruction."""
        persona_context = f"\nPersona/context about the sender:\n{persona}\n" if persona.strip() else ""
        prompt = f"""You are an email writing assistant. Based on the instruction below, compose a complete, proper email.

{persona_context}
Instruction: {instruction}

Return ONLY valid JSON:
{{
  "subject": "Email subject line",
  "body": "Full email body with greeting and sign-off",
  "to_hint": "recipient email if mentioned in instruction, else empty string",
  "schedule_hint": "scheduling time mentioned in instruction like 'tomorrow 12am', else empty string"
}}"""
        raw = self._call_model(prompt, settings=settings, retries=2, max_tokens=800)
        fallback = {
            "subject": "Email",
            "body": instruction,
            "to_hint": "",
            "schedule_hint": "",
        }
        if not raw:
            return fallback
        return self._parse_json_response(raw, fallback)

    def parse_schedule_time(self, time_str: str, settings: dict | None = None) -> str:
        """Parse a natural language time string into an ISO 8601 datetime string."""
        now = datetime.now(timezone.utc).isoformat()
        prompt = f"""Convert this scheduling instruction to an exact ISO 8601 datetime string (UTC).
Current UTC time is: {now}

Instruction: "{time_str}"

Return ONLY a valid ISO 8601 datetime string like: 2025-07-06T06:30:00+00:00
No explanation, no JSON, just the datetime string."""
        raw = self._call_model(prompt, settings=settings, retries=2, max_tokens=60)
        if raw:
            # Extract ISO datetime pattern
            match = re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', raw.strip())
            if match:
                return match.group(0) + "+00:00"
        return ""

    def detect_importance(self, subject: str, body: str, sender: str = "", settings: dict | None = None) -> dict:
        """Detect if an email is important and why."""
        prompt = f"""Analyze this email and determine if it is important (requires attention or action).

Subject: {subject}
From: {sender}
Body preview:
{(body or '')[:1000]}

Return ONLY valid JSON:
{{
  "is_important": true|false,
  "reason": "one sentence explaining why it is or is not important",
  "urgency": "high|medium|low"
}}"""
        raw = self._call_model(prompt, settings=settings, retries=1, max_tokens=200)
        fallback = {"is_important": False, "reason": "", "urgency": "low"}
        if not raw:
            return fallback
        return self._parse_json_response(raw, fallback)

    def match_auto_reply_rule(
        self,
        subject: str,
        body: str,
        sender: str,
        rules: list[dict],
        settings: dict | None = None,
        persona: str = "",
    ) -> dict | None:
        """Check if any auto-reply rule matches this email. Returns rule match or None."""
        if not rules:
            return None

        rules_text = "\n".join(
            f"Rule {i+1}: trigger_keywords={r.get('trigger_keywords', [])}, "
            f"reply_template={r.get('reply_template', '')}, "
            f"time_condition={r.get('time_condition', '')}, "
            f"rule_id={r.get('id', i)}"
            for i, r in enumerate(rules)
        )

        now_hour = datetime.now().hour

        prompt = f"""You are an email rule-matching assistant. Given an incoming email and a list of auto-reply rules, determine if any rule should be triggered.

Current hour (24h): {now_hour}

Incoming email:
Subject: {subject}
From: {sender}
Body: {(body or '')[:500]}

Rules:
{rules_text}

Persona/Sender details (Use this to personalize the reply): {persona}

Return ONLY valid JSON. If a rule matches, return:
{{
  "matched": true,
  "rule_id": <integer rule_id that matched>,
  "reply_text": "The exact reply text to send (from the rule template, adjusted for time condition if any)"
}}
If no rule matches:
{{
  "matched": false,
  "rule_id": null,
  "reply_text": ""
}}"""

        raw = self._call_model(prompt, settings=settings, retries=1, max_tokens=300)
        fallback = {"matched": False, "rule_id": None, "reply_text": ""}
        if not raw:
            return fallback
        result = self._parse_json_response(raw, fallback)
        return result if result.get("matched") else None

    def chat_about_mail(
        self,
        question: str,
        context_emails: list[dict],
        settings: dict | None = None,
        scope_label: str = "mail",
        history: list[dict] | None = None,
    ) -> str:
        context_block = self._build_context_block(context_emails)
        history_block = ""
        if history:
            history_lines = []
            for msg in history[-6:]:  # last 6 turns
                history_lines.append(f"User: {msg.get('user_message', '')}")
                history_lines.append(f"Assistant: {msg.get('agent_response', '')}")
            history_block = "\nCONVERSATION HISTORY:\n" + "\n".join(history_lines) + "\n"

        extra_instructions = "Respond in a concise, helpful way. If you suggest a reply, draft it plainly."
        if "summarize" in question.lower() or "summary" in question.lower() or "short" in question.lower() or "point" in question.lower():
            extra_instructions = "The user asked for a summary. You MUST provide a VERY SHORT, simple summary using a MAXIMUM of 3 concise bullet points. Do not write a long paragraph. End by asking if they need more info."

        prompt = f"""You are a helpful email assistant chatting about the user's {scope_label}.
Answer the user's question using only the provided mail context when possible.
If the answer is not in the context, say what is missing and suggest the next action.
{history_block}
MAIL CONTEXT:
{context_block}

QUESTION:
{question}

{extra_instructions}"""
        raw = self._call_model(prompt, settings=settings, retries=2, max_tokens=700)
        return raw.strip() if raw else "I could not generate a response."

    def parse_chat_intent(self, message: str, settings: dict | None = None) -> dict:
        """Parse chat message to determine if the user is asking to search for a specific person."""
        prompt = f"""You are a helpful AI assistant. Analyze the user's message to determine if they are mentioning or asking about emails related to a specific person, name, or contact.

Message: "{message}"

Return ONLY valid JSON.
If the user mentions ANY person's name (e.g. "What did John say?", "any mail related to riswanth", "Summarize Alice"):
{{
  "intent": "search_person",
  "name": "The extracted name (e.g. John, riswanth, Alice)"
}}
If they are NOT asking about any person (e.g. "Summarize my unread emails", "Write an email"):
{{
  "intent": "general",
  "name": null
}}"""
        raw = self._call_model(prompt, settings=settings, retries=1, max_tokens=100)
        fallback = {"intent": "general", "name": None}
        if not raw:
            return fallback
        return self._parse_json_response(raw, fallback)

    def test_provider(self, settings: dict | None = None) -> dict:
        resolved = self.resolve_settings(settings)
        provider = resolved["ai_provider"]
        try:
            raw = self._call_model(
                "Reply with exactly: ok",
                settings=resolved,
                retries=1,
                max_tokens=16,
                allow_fallback=False,
            )
            if not raw:
                raise RuntimeError("No response returned.")
            return {
                "success": True,
                "provider": provider,
                "model": self._model_name_for_provider(provider, resolved),
                "message": f"{provider.title()} model responded successfully.",
            }
        except Exception as exc:
            return {
                "success": False,
                "provider": provider,
                "model": self._model_name_for_provider(provider, resolved),
                "error": str(exc),
            }

    def test_specific_provider(self, provider: str, settings: dict | None = None) -> dict:
        """Test a specific provider (local or cloud) regardless of current setting."""
        resolved = self.resolve_settings(settings)
        resolved["ai_provider"] = provider
        resolved["force_provider"] = True
        return self.test_provider(resolved)

    def _call_model(
        self,
        prompt: str,
        settings: dict | None = None,
        retries: int = 3,
        max_tokens: int = 700,
        allow_fallback: bool = True,
    ) -> str:
        resolved = self.resolve_settings(settings)
        provider = resolved["ai_provider"]
        force_provider = resolved.get("force_provider", False)

        try:
            if provider == "local":
                return self._call_lmstudio(prompt, resolved, retries, max_tokens)
            return self._call_gemini(prompt, resolved, retries)
        except Exception:
            if allow_fallback and provider == "local" and not force_provider and config.GEMINI_API_KEY:
                return self._call_gemini(prompt, resolved, retries)
            raise

    def _call_lmstudio(self, prompt: str, settings: dict, retries: int, max_tokens: int) -> str:
        base_url = settings["local_base_url"].rstrip("/")
        endpoint = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
        model = settings.get("local_model") or self._detect_local_model(base_url)
        if not model:
            raise RuntimeError("No LM Studio model configured.")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }

        for attempt in range(retries):
            try:
                response = requests.post(endpoint, json=payload, timeout=60)
                response.raise_for_status()
                data = response.json()
                return self._extract_openai_content(data)
            except Exception as exc:
                if attempt == retries - 1:
                    raise RuntimeError(f"LM Studio request failed: {exc}") from exc
                time.sleep((2**attempt) * 2)
        return ""

    def _call_gemini(self, prompt: str, settings: dict, retries: int = 3) -> str:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        model_name = settings.get("cloud_model") or config.GEMINI_MODEL
        if not self._gemini_model or self._gemini_model_name != model_name:
            genai.configure(api_key=config.GEMINI_API_KEY)
            self._gemini_model_name = model_name
            self._gemini_model = genai.GenerativeModel(model_name)

        for attempt in range(retries):
            try:
                self._rate_limit()
                response = self._gemini_model.generate_content(prompt)
                return response.text
            except Exception as exc:
                if attempt == retries - 1:
                    raise RuntimeError(f"Gemini request failed: {exc}") from exc
                time.sleep((2**attempt) * 2)
        return ""

    def _rate_limit(self):
        self._request_count += 1
        now = time.time()
        elapsed = now - self._last_request_time
        if self._request_count % 14 == 0 and elapsed < 60:
            time.sleep(max(2, 62 - elapsed))
            self._request_count = 0
        self._last_request_time = time.time()

    def _parse_json_response(self, raw: str, fallback: dict) -> dict:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()
            data = json.loads(cleaned)
            if not isinstance(data, dict):
                return fallback

            priority = str(data.get("priority", fallback.get("priority", "normal"))).lower()
            category = str(data.get("category", fallback.get("category", "other"))).lower()
            if priority not in self.VALID_PRIORITIES:
                priority = fallback.get("priority", "normal")
            if category not in self.VALID_CATEGORIES:
                category = fallback.get("category", "other")
            data["priority"] = priority
            data["category"] = category
            return data
        except Exception:
            return fallback

    def _fallback_analysis(self, subject: str) -> dict:
        return {
            "priority": "normal",
            "priority_score": 3,
            "category": "other",
            "short_summary": subject or "No summary available.",
            "summary": subject or "No summary available.",
            "action_items": [],
            "key_points": [],
            "is_important": False,
        }

    def _build_context_block(self, emails: list[dict]) -> str:
        if not emails:
            return "No email context selected."
        lines = []
        for email in emails[:20]:
            lines.append(
                f"- [{email.get('id', '')}] {email.get('subject', '(No Subject)')} | "
                f"From: {email.get('sender', 'Unknown')} | "
                f"Priority: {email.get('priority', 'normal')} | "
                f"Category: {email.get('category', 'other')} | "
                f"Summary: {email.get('summary', '')}"
            )
        return "\n".join(lines)

    def _extract_openai_content(self, data: dict) -> str:
        if isinstance(data, dict):
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "") or choices[0].get("text", "")
            return data.get("output", "")
        return ""

    def _detect_local_model(self, base_url: str) -> str:
        try:
            endpoint = f"{base_url}/models" if base_url.endswith("/v1") else f"{base_url}/v1/models"
            response = requests.get(endpoint, timeout=4)
            response.raise_for_status()
            models = response.json().get("data", [])
            return models[0].get("id", "") if models else ""
        except Exception:
            return ""

    def _local_available(self, settings: dict | None = None) -> bool:
        base_url = (settings or {}).get("local_base_url") or config.LMSTUDIO_BASE_URL
        try:
            endpoint = f"{base_url.rstrip('/')}/models" if base_url.rstrip("/").endswith("/v1") else f"{base_url.rstrip('/')}/v1/models"
            return requests.get(endpoint, timeout=1.5).ok
        except Exception:
            return False

    def _model_name_for_provider(self, provider: str, settings: dict) -> str:
        return settings.get("local_model") if provider == "local" else settings.get("cloud_model") or config.GEMINI_MODEL
