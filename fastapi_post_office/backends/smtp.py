from __future__ import annotations

import smtplib
from email.message import EmailMessage as StdEmailMessage

from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailMessage

from .base import EmailBackend, SendResult


class SMTPBackend(EmailBackend):
    name = "smtp"

    def send(self, message: EmailMessage) -> SendResult:
        msg = StdEmailMessage()
        msg["Subject"] = message.subject
        msg["From"] = message.from_email
        msg["To"] = ", ".join(message.to_json)
        if message.cc_json:
            msg["Cc"] = ", ".join(message.cc_json)
        if message.bcc_json:
            msg["Bcc"] = ", ".join(message.bcc_json)

        if message.text_body and message.html_body:
            msg.set_content(message.text_body)
            msg.add_alternative(message.html_body, subtype="html")
        elif message.html_body:
            msg.add_alternative(message.html_body, subtype="html")
        else:
            msg.set_content(message.text_body or "")

        host = settings.smtp_host or ""
        try:
            with smtplib.SMTP(
                host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
            ) as client:
                if settings.smtp_starttls:
                    client.starttls()
                if settings.smtp_username and settings.smtp_password:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(msg)
            return SendResult(ok=True, provider_message_id="smtp")
        except Exception as exc:  # pragma: no cover - exercised in integration tests
            return SendResult(ok=False, error_message=str(exc))
