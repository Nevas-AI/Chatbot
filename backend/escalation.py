"""
escalation.py - Human Escalation Logic for Neva Chatbot
========================================================
Detects user frustration and triggers human agent escalation.
Logs escalation events and provides contact information.

Supports multi-client: accepts explicit config dict per client.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from dataclasses import dataclass

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class EscalationResponse:
    """Structured response for escalation events."""
    should_escalate: bool
    message: str
    email: str = ""
    phone: str = ""
    business_hours: str = ""
    trigger_keyword: str = ""


class EscalationHandler:
    """
    Handles detection and processing of human escalation requests.

    Supports multi-client: accepts explicit config dict so each
    client can have custom keywords, contact info, and business hours.
    """

    # Default keywords that trigger escalation (case-insensitive matching)
    DEFAULT_ESCALATION_KEYWORDS = [
        "speak to human",
        "speak to a human",
        "talk to human",
        "talk to a human",
        "real person",
        "real agent",
        "human agent",
        "live agent",
        "agent please",
        "agent",
        "manager",
        "speak to manager",
        "talk to manager",
        "supervisor",
        "not helpful",
        "useless",
        "terrible",
        "worst",
        "frustrated",
        "angry",
        "escalate",
        "complaint",
        "file a complaint",
        "not satisfied",
        "dissatisfied",
        "connect me to",
        "transfer me",
        "representative",
    ]

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize the escalation handler.

        Args:
            config: Optional dict with client-specific settings. Keys:
                - support_email, support_phone, business_hours, company_name
                - escalation_keywords (list override)
                If None, falls back to environment variables.
        """
        config = config or {}
        self.support_email = config.get("support_email", os.getenv("SUPPORT_EMAIL", "support@yourcompany.com"))
        self.support_phone = config.get("support_phone", os.getenv("SUPPORT_PHONE", "+91-XXXXXXXXXX"))
        self.business_hours = config.get("business_hours", os.getenv("BUSINESS_HOURS", "Mon-Fri 9AM-6PM IST"))
        self.company_name = config.get("company_name", os.getenv("COMPANY_NAME", "Your Company"))
        self.log_file = os.path.join(os.path.dirname(__file__), "escalations.log")

        # Allow per-client keyword override
        custom_keywords = config.get("escalation_keywords")
        if custom_keywords and isinstance(custom_keywords, list):
            self.escalation_keywords: List[str] = custom_keywords
        else:
            self.escalation_keywords = self.DEFAULT_ESCALATION_KEYWORDS

    def check_escalation(self, user_message: str) -> EscalationResponse:
        """
        Check if a user message triggers an escalation.

        Args:
            user_message: The user's message text

        Returns:
            EscalationResponse with escalation details
        """
        message_lower = user_message.lower().strip()

        # Check each keyword against the message
        triggered_keyword = None
        for keyword in self.escalation_keywords:
            if keyword in message_lower:
                triggered_keyword = keyword
                break

        if triggered_keyword:
            # Log the escalation
            self._log_escalation(user_message, triggered_keyword)

            if self.is_working_hours():
                escalation_message = "Would you like me to connect you with our customer support team?"
            else:
                escalation_message = (
                    f"I understand you'd like to speak with our team. Unfortunately, our "
                    f"live customer support is currently unavailable.\n\n"
                    f"🕐 **Working Hours:** {self.business_hours}\n"
                    f"📧 **Email:** {self.support_email}\n\n"
                    f"Please leave your query and contact details, and our team will get back to you during working hours."
                )

            return EscalationResponse(
                should_escalate=True,
                message=escalation_message,
                email=self.support_email,
                phone=self.support_phone,
                business_hours=self.business_hours,
                trigger_keyword=triggered_keyword,
            )

        # No escalation needed
        return EscalationResponse(
            should_escalate=False,
            message="",
        )

    def is_working_hours(self) -> bool:
        """Check if current time in IST is within Mon-Sat 9AM-6PM."""
        ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        if ist_now.weekday() < 6 and 9 <= ist_now.hour < 18:
            return True
        return False

    def force_escalate(self, reason: str = "User requested escalation") -> EscalationResponse:
        """Force an escalation (e.g., from the /api/escalate endpoint)."""
        self._log_escalation(reason, "manual_escalation")

        escalation_message = (
            f"I'm connecting you with our support team right away.\n\n"
            f"📧 **Email:** {self.support_email}\n"
            f"📞 **Phone:** {self.support_phone}\n"
            f"🕐 **Business Hours:** {self.business_hours}\n\n"
            f"A team member from {self.company_name} will assist you shortly."
        )

        return EscalationResponse(
            should_escalate=True,
            message=escalation_message,
            email=self.support_email,
            phone=self.support_phone,
            business_hours=self.business_hours,
            trigger_keyword="manual_escalation",
        )

    def _log_escalation(self, user_message: str, trigger: str) -> None:
        """Log an escalation event to the escalations.log file."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = (
                f"[{timestamp}] ESCALATION TRIGGERED\n"
                f"  Trigger: {trigger}\n"
                f"  Message: {user_message}\n"
                f"{'=' * 60}\n"
            )

            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)

            logger.info(f"Escalation logged: trigger='{trigger}', message='{user_message[:50]}...'")
        except Exception as e:
            logger.error(f"Failed to log escalation: {str(e)}")
