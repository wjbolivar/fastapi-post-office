from __future__ import annotations

import json
import urllib.request
from typing import Any

from fastapi_post_office.db.models import EmailMessage

from .base import EmailBackend, SendResult


class HttpApiBackend(EmailBackend):
    api_url: str = ""
    timeout_seconds: int = 10

    def build_payload(self, message: EmailMessage) -> dict[str, Any]:
        raise NotImplementedError

    def build_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def send(self, message: EmailMessage) -> SendResult:
        if not self.api_url:
            return SendResult(ok=False, error_message="API URL not configured")

        data = json.dumps(self.build_payload(message)).encode("utf-8")
        headers = self.build_headers()
        request = urllib.request.Request(self.api_url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if 200 <= status < 300:
                    return SendResult(ok=True, provider_message_id=str(status))
                return SendResult(ok=False, error_message=f"HTTP {status}")
        except Exception as exc:  # pragma: no cover
            return SendResult(ok=False, error_message=str(exc))
