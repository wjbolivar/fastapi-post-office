from __future__ import annotations

import json

from .base import EmailBackend, EmailPayload, SendResult


class ConsoleBackend(EmailBackend):
    name = "console"

    def send(self, message: EmailPayload) -> SendResult:
        payload: dict[str, str | None] = {"message_id": str(message.id), "backend": self.name}
        if self.config.log_body:
            payload.update(subject=message.subject, html=message.html_body, text=message.text_body)
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return SendResult(ok=True, provider_message_id="console")
