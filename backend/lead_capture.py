"""
lead_capture.py - Lead Extraction & Email Notification
======================================================
Extracts structured lead data (name, email, phone, company) from
chatbot conversations and sends lead notifications via Outlook SMTP.

Passwords are encrypted at rest using Fernet symmetric encryption.
"""

import os
import re
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime

from cryptography.fernet import Fernet
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Fernet encryption for app passwords
# ─────────────────────────────────────────────
_FERNET_KEY = os.getenv("FERNET_KEY")

def _get_fernet() -> Fernet:
    """Get a Fernet instance. Generates key on first run if missing."""
    global _FERNET_KEY
    if not _FERNET_KEY:
        _FERNET_KEY = Fernet.generate_key().decode()
        logger.warning(
            "⚠️ FERNET_KEY not found in .env. Generated a new key. "
            "Add this to your .env file to persist across restarts:\n"
            f"FERNET_KEY={_FERNET_KEY}"
        )
    return Fernet(_FERNET_KEY.encode() if isinstance(_FERNET_KEY, str) else _FERNET_KEY)


def encrypt_password(plain_password: str) -> str:
    """Encrypt a plain-text password using Fernet."""
    f = _get_fernet()
    return f.encrypt(plain_password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt a Fernet-encrypted password."""
    f = _get_fernet()
    return f.decrypt(encrypted_password.encode()).decode()


# ─────────────────────────────────────────────
# Lead data extraction
# ─────────────────────────────────────────────
@dataclass
class LeadData:
    """Structured lead information extracted from conversation."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    source_messages: List[Dict] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """Lead is 'complete' if we have a name + at least one contact method."""
        return bool(self.name and (self.email or self.phone))

    @property
    def has_any_data(self) -> bool:
        """True if we captured at least one field."""
        return bool(self.name or self.email or self.phone or self.company)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
        }


# Regex patterns for extracting lead info from user messages
EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE
)
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,5}[\s\-]?\d{3,5}"
)
# Structured markers the AI uses in its responses
LEAD_MARKER_PATTERN = re.compile(
    r"\[(?:LEAD_(NAME|EMAIL|PHONE|COMPANY|CONTEXT):\s*(.+?)|SHOW_LEAD_FORM)\]", re.IGNORECASE
)


def extract_lead_from_conversation(
    messages: List[Dict],
) -> LeadData:
    """
    Extract lead data from a conversation history.

    Strategy:
    1. First check for structured [LEAD_*: ...] markers in assistant messages
    2. Then scan user messages for email/phone patterns
    3. Use heuristics for name/company from user messages after the AI asked
    """
    lead = LeadData()
    lead.source_messages = messages[-20:] if len(messages) > 20 else messages[:]

    # Phase 1: Look for structured markers in assistant messages
    for msg in messages:
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            for match in LEAD_MARKER_PATTERN.finditer(content):
                field_name = match.group(1)
                if not field_name:
                    continue
                field_name = field_name.upper()
                value = match.group(2).strip()
                if field_name == "NAME" and not lead.name:
                    lead.name = value
                elif field_name == "EMAIL" and not lead.email:
                    lead.email = value
                elif field_name == "PHONE" and not lead.phone:
                    lead.phone = value
                elif field_name == "COMPANY" and not lead.company:
                    lead.company = value

    # Phase 2: Scan user messages for contact info patterns
    asked_for_details = False
    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        role = msg.get("role", "")

        # Detect when AI asked for lead details
        if role == "assistant" and any(
            kw in content.lower()
            for kw in [
                "your name",
                "email address",
                "contact number",
                "company name",
                "could i grab",
                "few quick details",
                "connect you with",
            ]
        ):
            asked_for_details = True

        # Parse user messages (especially after AI asked for details)
        if role == "user":
            # Always extract email and phone from any user message
            if not lead.email:
                email_match = EMAIL_PATTERN.search(content)
                if email_match:
                    lead.email = email_match.group(0)

            if not lead.phone:
                phone_match = PHONE_PATTERN.search(content)
                if phone_match:
                    candidate = phone_match.group(0).strip()
                    # Only accept if it looks like a real phone (>= 7 digits)
                    digits = re.sub(r"\D", "", candidate)
                    if len(digits) >= 7:
                        lead.phone = candidate

            # If AI asked for details, try to extract name/company from
            # user replies that are short sentences (likely providing info)
            if asked_for_details and len(content.strip()) < 200:
                lines = [
                    line.strip()
                    for line in content.split("\n")
                    if line.strip()
                ]
                for line in lines:
                    # Check for labeled info: "Name: John", "Company: Acme"
                    label_match = re.match(
                        r"(?:my\s+)?(?:name|full\s*name)\s*(?:is|:)\s*(.+)",
                        line,
                        re.IGNORECASE,
                    )
                    if label_match and not lead.name:
                        lead.name = label_match.group(1).strip().rstrip(".")
                        continue

                    company_match = re.match(
                        r"(?:my\s+)?(?:company|organization|org|business)\s*(?:name)?\s*(?:is|:)\s*(.+)",
                        line,
                        re.IGNORECASE,
                    )
                    if company_match and not lead.company:
                        lead.company = company_match.group(1).strip().rstrip(".")
                        continue

                    phone_label = re.match(
                        r"(?:my\s+)?(?:phone|contact|number|mobile|cell)\s*(?:number|no\.?)?\s*(?:is|:)\s*(.+)",
                        line,
                        re.IGNORECASE,
                    )
                    if phone_label and not lead.phone:
                        lead.phone = phone_label.group(1).strip().rstrip(".")
                        continue

                    email_label = re.match(
                        r"(?:my\s+)?(?:email|e-mail|mail)\s*(?:address|id)?\s*(?:is|:)\s*(.+)",
                        line,
                        re.IGNORECASE,
                    )
                    if email_label and not lead.email:
                        candidate_email = email_label.group(1).strip().rstrip(".")
                        if EMAIL_PATTERN.match(candidate_email):
                            lead.email = candidate_email
                        continue

    # Phase 3: Check for confirmation in assistant messages
    # (e.g., "Thanks, John! A consultant will reach out to you at john@...")
    for msg in messages:
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            confirm_match = re.search(
                r"(?:thanks|thank you),?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*!",
                content,
            )
            if confirm_match and not lead.name:
                lead.name = confirm_match.group(1).strip()

            # Try to pick up email from confirmation message
            if not lead.email:
                email_match = EMAIL_PATTERN.search(content)
                if email_match and "support@" not in email_match.group(0).lower():
                    lead.email = email_match.group(0)

    return lead


# ─────────────────────────────────────────────
# Email delivery (Outlook SMTP)
# ─────────────────────────────────────────────
OUTLOOK_SMTP_HOST = "smtp.office365.com"
OUTLOOK_SMTP_PORT = 587


def send_lead_email(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    lead: LeadData,
    company_name: str = "Your Company",
    bot_name: str = "Neva",
    full_history: Optional[List[Dict]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Send a lead notification email via Outlook SMTP.

    Args:
        sender_email: Outlook/Office365 address to send from
        sender_password: App Password for the account
        recipient_email: Email to send the lead details to
        lead: Extracted lead data
        company_name: Client company name (for email branding)
        bot_name: Bot name (for email branding)

    Returns:
        (success: bool, error_message: Optional[str])
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔔 New Lead Captured by {bot_name} - {lead.name or 'Unknown'}"
        msg["From"] = sender_email
        msg["To"] = recipient_email

        # Build HTML email body
        now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

        lead_rows = ""
        if lead.name:
            lead_rows += _email_row("👤 Name", lead.name)
        if lead.email:
            lead_rows += _email_row("📧 Email", f'<a href="mailto:{lead.email}">{lead.email}</a>')
        if lead.phone:
            lead_rows += _email_row("📞 Phone", f'<a href="tel:{lead.phone}">{lead.phone}</a>')
        if lead.company:
            lead_rows += _email_row("🏢 Company", lead.company)

        # Build AI Summary
        ai_summary_html = ""
        ai_summary_text_block = ""
        if full_history:
            try:
                # Basic Gemini model generation
                api_key = os.getenv("GEMINI_API_KEY")
                if api_key:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel("gemini-2.5-flash")
                    chat_text = "\n".join([f"{m.get('role', 'unknown').capitalize()}: {m.get('content', '')}" for m in full_history])
                    
                    prompt = (
                        f"You are an assistant for {company_name}. A new lead has been captured.\n"
                        f"Lead Name: {lead.name or 'Unknown'}\n\n"
                        f"Review the following chat history and provide a concise, professional summary (3-4 sentences) "
                        f"of what the lead is looking for, their pain points, and any relevant context for the sales team.\n\n"
                        f"Chat History:\n{chat_text}\n\nSummary:"
                    )
                    
                    response = model.generate_content(prompt)
                    summary_text = response.text.strip()
                    
                    ai_summary_html = (
                        f"<div style='background: #eef2ff; border-left: 4px solid #4f46e5; padding: 16px; margin-top: 24px; border-radius: 4px;'>"
                        f"<h3 style='color: #4f46e5; margin-top: 0; font-size: 16px;'>🤖 AI Summary</h3>"
                        f"<p style='color: #374151; margin: 0; font-size: 14px; line-height: 1.5;'>{summary_text}</p>"
                        f"</div>"
                    )
                    ai_summary_text_block = f"\nAI Summary:\n{summary_text}\n"
            except Exception as e:
                logger.error(f"Failed to generate lead summary: {e}")

        # Build conversation excerpt
        conversation_html = ""
        messages_to_show = full_history if full_history is not None else lead.source_messages[-10:]
        
        if messages_to_show:
            conversation_html = "<h3 style='color: #374151; margin-top: 24px;'>💬 Conversation History</h3>"
            conversation_html += "<div style='background: #f9fafb; border-radius: 8px; padding: 16px; margin-top: 8px; max-height: 400px; overflow-y: auto;'>"
            for m in messages_to_show:
                role = m.get("role", "unknown")
                content = m.get("content", "")
                if role == "user":
                    conversation_html += f"<p style='margin: 8px 0;'><strong style='color: #2563eb;'>User:</strong> {content}</p>"
                elif role == "assistant":
                    conversation_html += f"<p style='margin: 8px 0;'><strong style='color: #7c3aed;'>{bot_name}:</strong> {content}</p>"
            conversation_html += "</div>"
        
        html_body = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 24px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 20px;">🔔 New Lead Captured</h1>
                    <p style="color: rgba(255,255,255,0.85); margin: 8px 0 0 0; font-size: 14px;">{company_name} • {now}</p>
                </div>
                <div style="padding: 24px;">
                    <h2 style="color: #1f2937; margin: 0 0 16px 0; font-size: 18px;">Lead Details</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        {lead_rows}
                    </table>
                    {ai_summary_html}
                    {conversation_html}
                </div>
                <div style="background: #f9fafb; padding: 16px; text-align: center; border-top: 1px solid #e5e7eb;">
                    <p style="color: #9ca3af; font-size: 12px; margin: 0;">
                        Captured by {bot_name} • {company_name} Chatbot
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
New Lead Captured by {bot_name}
{company_name} • {now}

Lead Details:
- Name: {lead.name or 'Not provided'}
- Email: {lead.email or 'Not provided'}
- Phone: {lead.phone or 'Not provided'}
- Company: {lead.company or 'Not provided'}
{ai_summary_text_block}
"""

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Send via Outlook SMTP
        with smtplib.SMTP(OUTLOOK_SMTP_HOST, OUTLOOK_SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        logger.info(f"✅ Lead email sent to {recipient_email} for lead: {lead.name}")
        return True, None

    except smtplib.SMTPAuthenticationError:
        error = "Outlook authentication failed. Check email address and app password."
        logger.error(f"❌ {error}")
        return False, error
    except smtplib.SMTPException as e:
        error = f"SMTP error: {str(e)}"
        logger.error(f"❌ {error}")
        return False, error
    except Exception as e:
        error = f"Email sending failed: {str(e)}"
        logger.error(f"❌ {error}")
        return False, error


def send_thank_you_email(
    sender_email: str,
    sender_password: str,
    lead: LeadData,
    company_name: str = "Your Company",
    bot_name: str = "Neva",
    full_history: Optional[List[Dict]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Send a dynamic AI-generated thank you email to the captured lead.
    """
    if not lead.email:
        return False, "No recipient email provided."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Thank you for reaching out to {company_name}"
        msg["From"] = sender_email
        msg["To"] = lead.email

        # Generate AI Thank You message
        thank_you_text_block = "Thank you for reaching out! We have received your details and our team will contact you shortly."
        thank_you_html = f"<p style='color: #374151; font-size: 16px; line-height: 1.6;'>{thank_you_text_block}</p>"

        if full_history:
            try:
                api_key = os.getenv("GEMINI_API_KEY")
                if api_key:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel("gemini-2.5-flash")
                    chat_text = "\n".join([f"{m.get('role', 'unknown').capitalize()}: {m.get('content', '')}" for m in full_history])
                    
                    prompt = (
                        f"You are {bot_name}, an assistant for {company_name}.\n"
                        f"A user named {lead.name or 'there'} has just provided their contact details to be contacted by sales/support.\n\n"
                        f"Review the following chat history and write a warm, personalized 2-3 sentence 'Thank You' email body addressed to the user. "
                        f"Acknowledge their specific needs based on the chat (e.g., 'Thank you for reaching out about upgrading your ERP system...'). "
                        f"Assure them that a specialist from {company_name} will be in touch shortly.\n"
                        f"Important: Do NOT include subject lines, placeholders, or email signatures (no 'Best regards, XYZ'). Just write the exact plain-text paragraphs to be used as the email body.\n\n"
                        f"Chat History:\n{chat_text}\n\nEmail Body:"
                    )
                    
                    response = model.generate_content(prompt)
                    ai_text = response.text.strip()
                    if ai_text:
                        thank_you_text_block = ai_text
                        html_formatted = ai_text.replace("\n", "<br>")
                        thank_you_html = f"<p style='color: #374151; font-size: 16px; line-height: 1.6;'>{html_formatted}</p>"
            except Exception as e:
                logger.error(f"Failed to generate lead thank you message: {e}")

        greeting = f"Hi {lead.name}," if lead.name else "Hi there,"

        html_body = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="background: linear-gradient(135deg, #4f46e5, #7c3aed); padding: 32px 24px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 24px;">Thank You!</h1>
                </div>
                <div style="padding: 32px 24px;">
                    <p style="color: #1f2937; font-size: 18px; font-weight: 500; margin-top: 0;">{greeting}</p>
                    {thank_you_html}
                    <p style="color: #6b7280; font-size: 14px; margin-top: 32px; border-top: 1px solid #e5e7eb; padding-top: 16px;">
                        Best regards,<br>
                        <strong>The {company_name} Team</strong>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""{greeting}

{thank_you_text_block}

Best regards,
The {company_name} Team
"""

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(OUTLOOK_SMTP_HOST, OUTLOOK_SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        logger.info(f"✅ Thank you email sent to {lead.email} for lead: {lead.name}")
        return True, None

    except smtplib.SMTPAuthenticationError:
        error = "Outlook authentication failed. Check email address and app password."
        logger.error(f"❌ {error}")
        return False, error
    except Exception as e:
        error = f"Thank you email sending failed: {str(e)}"
        logger.error(f"❌ {error}")
        return False, error


def _email_row(label: str, value: str) -> str:
    """Build a table row for the HTML email."""
    return f"""
    <tr>
        <td style="padding: 10px 12px; border-bottom: 1px solid #f3f4f6; color: #6b7280; font-size: 14px; width: 120px; vertical-align: top;">
            {label}
        </td>
        <td style="padding: 10px 12px; border-bottom: 1px solid #f3f4f6; color: #1f2937; font-size: 14px; font-weight: 500;">
            {value}
        </td>
    </tr>
    """


def send_test_email(
    sender_email: str,
    sender_password: str,
    company_name: str = "Your Company",
) -> tuple[bool, Optional[str]]:
    """
    Send a test email to verify Outlook SMTP configuration.

    Args:
        sender_email: Outlook/Office365 address
        sender_password: App Password for the account
        company_name: Company name for branding

    Returns:
        (success: bool, error_message: Optional[str])
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✅ {company_name} Chatbot - Email Configuration Test"
        msg["From"] = sender_email
        msg["To"] = sender_email

        html = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 20px;">
            <div style="max-width: 500px; margin: 0 auto; text-align: center; padding: 40px; background: #f0fdf4; border: 2px solid #86efac; border-radius: 12px;">
                <h1 style="color: #16a34a; margin: 0;">✅ Configuration Successful!</h1>
                <p style="color: #374151; margin: 16px 0 0 0;">
                    Your email settings for <strong>{company_name}</strong> chatbot are working correctly.
                    Lead notifications will be sent to this email address.
                </p>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(OUTLOOK_SMTP_HOST, OUTLOOK_SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        logger.info(f"✅ Test email sent successfully to {sender_email}")
        return True, None

    except smtplib.SMTPAuthenticationError:
        error = "Outlook authentication failed. Check email and app password."
        logger.error(f"❌ {error}")
        return False, error
    except Exception as e:
        error = f"Email test failed: {str(e)}"
        logger.error(f"❌ {error}")
        return False, error
