from __future__ import annotations

import json

from fastapi_post_office.db.models import EmailMessage

from .base import EmailBackend, SendResult


class ConsoleBackend(EmailBackend):
    name = "console"

    def send(self, message: EmailMessage) -> SendResult:
        payload = {
            "to": message.to_json,
            "cc": message.cc_json,
            "bcc": message.bcc_json,
            "subject": message.subject,
            "html": message.html_body,
            "text": message.text_body,
        }
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return SendResult(ok=True, provider_message_id="console")
