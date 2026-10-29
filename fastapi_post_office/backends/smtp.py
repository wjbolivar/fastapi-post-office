from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage as StdEmailMessage
from email.utils import make_msgid

from .base import EmailBackend, EmailPayload, SendResult


class SMTPBackend(EmailBackend):
    name = "smtp"

    def send(self, message: EmailPayload) -> SendResult:
        if self.config.smtp_username and not self.config.smtp_starttls:
            return SendResult(
                ok=False, retryable=False, error_message="SMTP authentication requires STARTTLS"
            )
        msg = StdEmailMessage()
        msg["Message-ID"] = make_msgid(idstring=str(message.id))
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

        host = self.config.smtp_host or ""
        delivery_started = False
        try:
            with smtplib.SMTP(
                host, self.config.smtp_port, timeout=self.config.smtp_timeout_seconds
            ) as client:
                if self.config.smtp_starttls:
                    client.starttls(context=ssl.create_default_context())
                if self.config.smtp_username and self.config.smtp_password:
                    client.login(self.config.smtp_username, self.config.smtp_password)
                delivery_started = True
                refused = client.send_message(msg)
                if refused:
                    # Some recipients already accepted: retrying the whole message duplicates mail.
                    return SendResult(
                        ok=False,
                        retryable=False,
                        error_message="Partial SMTP delivery; manual reconciliation required",
                        error_code="partial_delivery",
                    )
            return SendResult(ok=True, provider_message_id=str(msg["Message-ID"]))
        except smtplib.SMTPResponseException as exc:
            return SendResult(
                ok=False,
                retryable=400 <= exc.smtp_code < 500,
                error_code=f"smtp_{exc.smtp_code}",
                error_message=f"SMTP {exc.smtp_code}",
            )
        except smtplib.SMTPRecipientsRefused as exc:
            retryable = all(400 <= code < 500 for code, _ in exc.recipients.values())
            return SendResult(
                ok=False,
                retryable=retryable,
                error_code="recipients_refused",
                error_message="SMTP recipients refused",
            )
        except Exception as exc:  # pragma: no cover - exercised in integration tests
            return SendResult(
                ok=False,
                retryable=not delivery_started,
                ambiguous=delivery_started,
                error_code="transport_unknown" if delivery_started else "connection_failed",
                error_message=f"SMTP error: {type(exc).__name__}",
            )
