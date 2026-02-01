from __future__ import annotations

from typing import Any

from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailMessage

from .http_base import HttpApiBackend


class SendPulseBackend(HttpApiBackend):
    name = "sendpulse"
    api_url = settings.sendpulse_base_url

    def build_headers(self) -> dict[str, str]:
        token = settings.sendpulse_api_token
        if not token:
            raise RuntimeError("SENDPULSE_API_TOKEN is required")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def build_payload(self, message: EmailMessage) -> dict[str, Any]:
        sender = {"email": message.from_email}
        if settings.sendpulse_from_name:
            sender["name"] = settings.sendpulse_from_name

        to_list = [{"email": email} for email in message.to_json]
        payload: dict[str, Any] = {
            "email": {
                "subject": message.subject,
                "from": sender,
                "to": to_list,
            }
        }
        if message.html_body:
            payload["email"]["html"] = message.html_body
        if message.text_body:
            payload["email"]["text"] = message.text_body
        return payload
