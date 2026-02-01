from __future__ import annotations

from typing import Any

from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailMessage

from .http_base import HttpApiBackend


class PostmarkBackend(HttpApiBackend):
    name = "postmark"
    api_url = settings.postmark_base_url

    def build_headers(self) -> dict[str, str]:
        token = settings.postmark_server_token
        if not token:
            raise RuntimeError("POSTMARK_SERVER_TOKEN is required")
        return {
            "X-Postmark-Server-Token": token,
            "Content-Type": "application/json",
        }

    def build_payload(self, message: EmailMessage) -> dict[str, Any]:
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
