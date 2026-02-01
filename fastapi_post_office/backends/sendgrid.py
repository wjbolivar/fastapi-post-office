from __future__ import annotations

from typing import Any

from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailMessage

from .http_base import HttpApiBackend


class SendGridBackend(HttpApiBackend):
    name = "sendgrid"
    api_url = settings.sendgrid_base_url

    def build_headers(self) -> dict[str, str]:
        api_key = settings.sendgrid_api_key
        if not api_key:
            raise RuntimeError("SENDGRID_API_KEY is required")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def build_payload(self, message: EmailMessage) -> dict[str, Any]:
        personalization: dict[str, Any] = {
            "to": [{"email": email} for email in message.to_json],
        }
        if message.cc_json:
            personalization["cc"] = [{"email": email} for email in message.cc_json]
        if message.bcc_json:
            personalization["bcc"] = [{"email": email} for email in message.bcc_json]

        content = []
        if message.text_body:
            content.append({"type": "text/plain", "value": message.text_body})
        if message.html_body:
            content.append({"type": "text/html", "value": message.html_body})

        return {
            "personalizations": [personalization],
            "from": {"email": message.from_email},
            "subject": message.subject,
            "content": content,
        }
