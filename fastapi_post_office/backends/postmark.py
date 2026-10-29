from __future__ import annotations

from typing import Any

from .base import EmailPayload, SendResult
from .http_base import HttpApiBackend


class PostmarkBackend(HttpApiBackend):
    name = "postmark"

    def __init__(self, *, config=None):
        super().__init__(config=config)
        self.api_url = self.config.postmark_base_url

    def build_headers(self) -> dict[str, str]:
        token = self.config.postmark_server_token
        if not token:
            raise RuntimeError("POSTMARK_SERVER_TOKEN is required")
        return {
            "X-Postmark-Server-Token": token,
            "Content-Type": "application/json",
        }

    def build_payload(self, message: EmailPayload) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "From": message.from_email,
            "To": ", ".join(message.to_json),
            "Subject": message.subject,
        }
        if message.cc_json:
            payload["Cc"] = ", ".join(message.cc_json)
        if message.bcc_json:
            payload["Bcc"] = ", ".join(message.bcc_json)
        if message.text_body:
            payload["TextBody"] = message.text_body
        if message.html_body:
            payload["HtmlBody"] = message.html_body
        return payload

    def parse_success(self, response) -> SendResult:
        data = self.read_json(response)
        code = data["ErrorCode"]
        if code != 0:
            return SendResult(
                ok=False,
                retryable=False,
                error_code=f"postmark_{code}",
                error_message="Postmark rejected message",
            )
        message_id = data["MessageID"]
        if not isinstance(message_id, str) or not message_id or len(message_id) > 255:
            raise ValueError("Invalid provider message ID")
        return SendResult(ok=True, provider_message_id=message_id)
