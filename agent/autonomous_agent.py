"""
Autonomous Agent - Intelligent task suggestions, draft replies, rules engine, and importance detection.
"""

import json
from datetime import datetime
from agent.ai_engine import AIEngine
from agent.db_manager import DBManager


class AutonomousAgent:
    """Autonomous AI agent for task suggestions and email handling."""

    TASK_TYPES = {
        "reply": "Reply to email",
        "follow_up": "Follow up action",
        "schedule": "Schedule meeting/event",
        "review": "Review document",
        "urgent": "Urgent action needed",
        "reminder": "Set reminder",
        "delegate": "Delegate to someone",
    }

    SCOPES = {
        "personal": "Informal and friendly tone",
        "professional": "Professional business tone",
        "formal": "Formal and corporate tone",
        "urgent": "Direct and action-oriented",
        "casual": "Relaxed and conversational",
    }

    def __init__(self):
        self.ai_engine = AIEngine()
        self.db = DBManager()

    def analyze_email_for_tasks(self, email: dict, settings: dict = None) -> list[dict]:
        """Analyze an email and suggest relevant tasks."""
        tasks = []
        subject = email.get("subject", "").lower()
        body = email.get("body", "").lower()
        category = email.get("category", "")
        priority = email.get("priority", "")

        if "hr" in subject or "hr" in body or "meeting" in subject or "performance" in subject:
            tasks.append({
                "type": "reply",
                "title": "Reply to HR Meeting",
                "description": f"Respond to {email.get('sender', 'sender')} regarding {email.get('subject', 'email')}, confirm attendance and dress code compliance",
                "priority": "high" if priority == "critical" else "normal",
            })
            tasks.append({
                "type": "schedule",
                "title": "Add to Calendar",
                "description": "Schedule meeting in your calendar and set reminder",
                "priority": "normal",
            })

        if category == "finance" or "payment" in subject or "invoice" in subject:
            tasks.append({
                "type": "review",
                "title": "Review Financial Document",
                "description": "Review the attached invoice/payment details for accuracy",
                "priority": priority,
            })
            if "payment" in subject.lower():
                tasks.append({
                    "type": "follow_up",
                    "title": "Process Payment",
                    "description": "Process payment according to invoice terms",
                    "priority": "high" if "urgent" in subject.lower() else "normal",
                })

        if category == "work" or "project" in subject or "deadline" in subject:
            tasks.append({
                "type": "follow_up",
                "title": "Action Item",
                "description": f"Follow up on action items from {email.get('sender', 'sender')}",
                "priority": priority,
            })

        if category == "security" or "password" in subject or "2fa" in subject:
            tasks.append({
                "type": "urgent",
                "title": "Security Action Required",
                "description": "Take immediate action on security alert",
                "priority": "critical",
            })

        if category == "promotion" or category == "newsletter":
            tasks.append({
                "type": "review",
                "title": "Review Promotional Content",
                "description": "Review and decide if relevant",
                "priority": "low",
            })

        return tasks

    def generate_draft_reply(self, email: dict, scope: str = "professional", settings: dict = None) -> dict:
        """Generate a draft reply to an email based on its content."""
        subject = email.get("subject", "")
        body = email.get("body", "")
        sender = email.get("sender", "")

        scope_info = self.SCOPES.get(scope, "professional")

        prompt = f"""You are an email assistant. Generate a professional draft reply to this email.

SCOPE/TONE: {scope_info}

ORIGINAL EMAIL:
From: {sender}
Subject: {subject}
Body: {body[:1000]}

Generate a draft reply that:
1. Is appropriate for the scope: {scope}
2. Addresses the main points in the email
3. Is concise but complete
4. Includes a proper greeting and sign-off

RESPOND WITH ONLY the draft email body (no subject line, no meta-commentary):"""

        try:
            draft_text = self.ai_engine._call_model(prompt, settings=settings)

            subject_prompt = f"Generate a brief email subject line for a reply to: {subject}. Reply with ONLY the subject line, no quotes or explanation."
            reply_subject = self.ai_engine._call_model(subject_prompt, settings=settings, max_tokens=50)

            return {
                "success": True,
                "draft_body": draft_text.strip() if draft_text else "",
                "draft_subject": f"Re: {reply_subject.strip() if reply_subject else subject}",
                "confidence": 0.85,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "draft_body": "",
                "draft_subject": f"Re: {subject}",
            }

    def generate_chat_response(self, user_message: str, email: dict = None, scope: str = "professional",
                                settings: dict = None, history: list = None) -> dict:
        """Generate a chat response about an email with smart disambiguation."""
        
        # Check if we need to search for matching emails (no specific email provided)
        context = ""
        matching_emails = []
        
        if email:
            context = f"""
CURRENT EMAIL CONTEXT:
- Subject: {email.get('subject', '')}
- From: {email.get('sender', '')}
- Category: {email.get('category', '')}
- Priority Score: {email.get('priority_score', 3)}
- Summary: {email.get('summary', '')}
"""
        else:
            # Search for matching emails based on user query
            search_terms = self._extract_search_terms(user_message)
            
            if search_terms:
                all_emails = self.db.get_emails(account=None, limit=100)
                matching_emails = [e for e in all_emails 
                                  if any(term.lower() in (e.get('subject', '').lower() + ' ' + e.get('sender', '')).lower() 
                                          for term in search_terms)]
                
                # If multiple matches found, provide interactive options
                if len(matching_emails) > 1:
                    return self._generate_disambiguation_response(user_message, matching_emails, scope, settings, history)
        
        history_block = ""
        if history:
            lines = []
            for msg in history[-6:]:
                lines.append(f"User: {msg.get('user_message', '')}")
                lines.append(f"Assistant: {msg.get('agent_response', '')}")
            history_block = "\nPrevious messages:\n" + "\n".join(lines) + "\n"

        scope_info = self.SCOPES.get(scope, "professional")

        detailed_keywords = ["detail", "elaborate", "full", "explain", "in-depth", "complete"]
        is_detail_requested = any(kw in user_message.lower() for kw in detailed_keywords)

        if is_detail_requested:
            instructions = "Provide a detailed, comprehensive response."
        else:
            instructions = "Keep the response extremely short, crisp, and to the point. Provide a maximum of 2 sentences or minimal bullet points. Do not write long paragraphs. If they want detailed info, they will ask for it."

        prompt = f"""You are a helpful email assistant. Answer the user's question about their email in a {scope} manner.

{context}
{history_block}
User: {user_message}

{instructions}
Focus on being practical and actionable."""

        try:
            response = self.ai_engine._call_model(prompt, settings=settings, max_tokens=300)
            
            # If we found matching emails but didn't get a specific email context, 
            # provide general summary with options to select specific email
            if not email and matching_emails:
                return {
                    "success": True,
                    "response": self._generate_general_response(user_message, matching_emails),
                    "has_options": True,
                    "options": [{"label": f"Email #{e['id']}: {e.get('subject', 'No Subject')}", "action": f"/info_email {e['id']}|{e.get('subject', 'No Subject')}"} 
                               for e in matching_emails[:5]],  # Show top 5 options
                    "email_count": len(matching_emails)
                }
            
            return {
                "success": True,
                "response": response.strip() if response else "I'm unable to process that request. Please try again.",
                "has_options": False,
                "options": [],
                "email_count": 1
            }
        except Exception as e:
            return {
                "success": False,
                "response": f"I encountered an error: {str(e)}",
                "has_options": False,
                "options": [],
                "email_count": 0
            }

    def _extract_search_terms(self, user_message: str) -> list:
        """Extract search terms from user message."""
        # Remove common phrases and extract keywords
        cleaned = user_message.lower()
        
        # Common phrases to ignore
        phrases_to_ignore = [
            "about", "regarding", "tell me about", "what do you know", 
            "information on", "details of", "summary of"
        ]
        
        terms = []
        for phrase in phrases_to_ignore:
            cleaned = cleaned.replace(phrase, "").strip()
        
        # Extract names and keywords
        import re
        # Find potential email subjects/keywords (words with 3+ letters)
        words = re.findall(r'\b[a-z]{3,}\b', cleaned)
        terms = [w for w in words if len(w) >= 3]
        
        return list(set(terms))[:10]  # Limit to top 10 terms

    def _generate_disambiguation_response(self, user_message: str, matching_emails: list, 
                                          scope: str = "professional", settings: dict = None, history: list = None) -> dict:
        """Generate response when multiple emails match."""
        
        # Get summary info for all matching emails
        summaries = []
        for email in matching_emails[:5]:  # Show top 5
            sender_name = self._get_sender_name(email.get('sender', ''))
            subject_preview = email.get('subject', 'No Subject')
            date_info = email.get('date', '')[:10] if email.get('date') else 'Unknown'
            summaries.append(f"{sender_name}: {subject_preview} ({date_info})")

        response_text = (f"I found multiple emails related to your query. Here are the most relevant ones:\n\n"
                         f"{chr(10).join(summaries)}\n\n"
                         "Click on any email above to get detailed information about it.")

        return {
            "success": True,
            "response": response_text,
            "has_options": True,
            "options": [{"label": f"Email #{e['id']}: {e.get('subject', 'No Subject')}", "action": f"/info_email {e['id']}|{e.get('subject', 'No Subject')}"} 
                        for e in matching_emails[:5]],
            "email_count": len(matching_emails)
        }

    def _generate_general_response(self, user_message: str, matching_emails: list) -> str:
        """Generate general response when multiple emails match."""
        
        # Get recent activity summary
        recent_summaries = []
        for email in matching_emails[:3]:  # Show top 3 most relevant
            sender_name = self._get_sender_name(email.get('sender', ''))
            subject_preview = email.get('subject', '').split()[0] if email.get('subject') else 'No Subject'
            recent_summaries.append(f"{sender_name}: {subject_preview}")

        return (f"I found several emails related to your query. Here's a quick overview:\n\n"
                f"{chr(10).join(recent_summaries)}\n\n"
                "Would you like me to provide more details about any specific email? Just let me know which one interests you most.")

    def _get_sender_name(self, sender: str) -> str:
        """Extract name from sender field."""
        if not sender:
            return "Unknown"
        
        # Handle format: "Name <email@domain.com>" or just email
        parts = sender.split('<')
        if len(parts) > 0:
            name_part = parts[0].split('>')
            return name_part[0].strip() if name_part else sender
        
        return sender

    def process_incoming_email(self, email: dict, rules: list[dict], settings: dict = None, persona: str = "") -> dict:
        """
        Process an incoming email through the rules engine and importance detection.
        Returns a dict with keys: matched_rule, reply_text, is_important, importance_reason
        """
        result = {
            "matched_rule": None,
            "reply_text": None,
            "is_important": False,
            "importance_reason": "",
        }

        # Check importance
        importance = self.ai_engine.detect_importance(
            subject=email.get("subject", ""),
            body=email.get("body", ""),
            sender=email.get("sender", ""),
            settings=settings,
        )
        result["is_important"] = importance.get("is_important", False)
        result["importance_reason"] = importance.get("reason", "")

        # Check rules engine
        if rules:
            rule_match = self.ai_engine.match_auto_reply_rule(
                subject=email.get("subject", ""),
                body=email.get("body", ""),
                sender=email.get("sender", ""),
                rules=rules,
                settings=settings,
                persona=persona,
            )
            if rule_match and rule_match.get("matched"):
                result["matched_rule"] = rule_match.get("rule_id")
                result["reply_text"] = rule_match.get("reply_text", "")

        return result

    def smart_categorize_email(self, email: dict) -> dict:
        """Provide smart categorization insights."""
        return {
            "category": email.get("category", "unknown"),
            "priority": email.get("priority", "normal"),
            "summary": email.get("summary", ""),
            "action_suggested": self._get_action_suggestion(email),
        }

    def _get_action_suggestion(self, email: dict) -> str:
        """Get a suggested action based on email content."""
        category = email.get("category", "")
        priority = email.get("priority", "")
        subject = email.get("subject", "").lower()

        if priority == "critical":
            return "⚠️ URGENT: Requires immediate attention"
        elif category == "work":
            if "meeting" in subject:
                return "📅 Schedule this meeting"
            elif "deadline" in subject:
                return "⏰ Mark deadline in calendar"
            else:
                return "✉️ Reply required"
        elif category == "finance":
            return "💰 Review financial details"
        elif category == "security":
            return "🔒 Security action needed"
        elif category == "personal":
            return "👤 Personal correspondence"
        elif category == "promotion":
            return "🏷️ Marketing/promotional content"
        else:
            return "📧 File or archive"
