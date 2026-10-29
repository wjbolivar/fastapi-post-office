from __future__ import annotations

import base64
from typing import Any

from .base import EmailPayload, SendResult
from .http_base import HttpApiBackend


class SendPulseBackend(HttpApiBackend):
    name = "sendpulse"

    def __init__(self, *, config=None):
        super().__init__(config=config)
        self.api_url = self.config.sendpulse_base_url

    def build_headers(self) -> dict[str, str]:
        token = self.config.sendpulse_api_token
        if not token:
            raise RuntimeError("SENDPULSE_API_TOKEN is required")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def build_payload(self, message: EmailPayload) -> dict[str, Any]:
        sender = {"email": message.from_email}
        if self.config.sendpulse_from_name:
            sender["name"] = self.config.sendpulse_from_name

        to_list = [{"email": email} for email in message.to_json]
        payload: dict[str, Any] = {
            "email": {
                "subject": message.subject,
                "from": sender,
                "to": to_list,
            }
        }
        if message.html_body:
            payload["email"]["html"] = base64.b64encode(message.html_body.encode("utf-8")).decode(
                "ascii"
            )
        if message.text_body:
            payload["email"]["text"] = message.text_body
        if message.cc_json:
            payload["email"]["cc"] = [{"email": email} for email in message.cc_json]
        if message.bcc_json:
            payload["email"]["bcc"] = [{"email": email} for email in message.bcc_json]
        return payload

    def parse_success(self, response) -> SendResult:
        data = self.read_json(response)
        if data.get("result") is False:
            return SendResult(
                ok=False,
                retryable=False,
                error_code="sendpulse_rejected",
                error_message="SendPulse rejected message",
            )
        if data.get("result") is not True:
            raise ValueError("Invalid provider response")
        message_id = data["id"]
        if not isinstance(message_id, str) or not message_id or len(message_id) > 255:
            raise ValueError("Invalid provider message ID")
        return SendResult(ok=True, provider_message_id=message_id)
