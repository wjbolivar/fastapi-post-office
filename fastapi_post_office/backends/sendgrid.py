from __future__ import annotations

from typing import Any

from .base import EmailPayload, SendResult
from .http_base import HttpApiBackend


class SendGridBackend(HttpApiBackend):
    name = "sendgrid"

    def __init__(self, *, config=None):
        super().__init__(config=config)
        self.api_url = self.config.sendgrid_base_url

    def build_headers(self) -> dict[str, str]:
        api_key = self.config.sendgrid_api_key
        if not api_key:
            raise RuntimeError("SENDGRID_API_KEY is required")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def build_payload(self, message: EmailPayload) -> dict[str, Any]:
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

    def parse_success(self, response) -> SendResult:
        message_id = response.headers.get("X-Message-Id")
        return SendResult(ok=True, provider_message_id=message_id)
