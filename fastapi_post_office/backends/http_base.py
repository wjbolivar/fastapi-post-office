from __future__ import annotations

import json
import urllib.request
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit

from .base import EmailBackend, EmailPayload, SendResult


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpApiBackend(EmailBackend):
    api_url: str = ""
    timeout_seconds: int = 10

    def build_payload(self, message: EmailPayload) -> dict[str, Any]:
        raise NotImplementedError

    def build_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def parse_success(self, response) -> SendResult:
        return SendResult(ok=True)

    @staticmethod
    def read_json(response) -> dict[str, Any]:
        # Bound untrusted provider responses; never persist their free-form error text.
        raw = response.read(65_537)
        if len(raw) > 65_536:
            raise ValueError("Provider response too large")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Provider response must be an object")
        return data

    def send(self, message: EmailPayload) -> SendResult:
        if not self.api_url:
            return SendResult(ok=False, error_message="API URL not configured")

        parsed = urlsplit(self.api_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return SendResult(
                ok=False,
                retryable=False,
                error_message="API URL must use HTTPS without credentials",
            )

        try:
            data = json.dumps(self.build_payload(message)).encode("utf-8")
            headers = self.build_headers()
            request = urllib.request.Request(
                self.api_url, data=data, headers=headers, method="POST"
            )
        except (ValueError, TypeError, RuntimeError):
            return SendResult(
                ok=False,
                retryable=False,
                error_code="configuration_error",
                error_message="Invalid provider configuration or payload",
            )

        try:
            with urllib.request.build_opener(_NoRedirect()).open(
                request, timeout=self.timeout_seconds
            ) as response:
                status = getattr(response, "status", 200)
                if 200 <= status < 300:
                    try:
                        return self.parse_success(response)
                    except (ValueError, TypeError, KeyError):
                        return SendResult(
                            ok=False,
                            retryable=False,
                            ambiguous=True,
                            error_code="invalid_response",
                            error_message="Unrecognized provider acceptance response",
                        )
                return SendResult(ok=False, error_message=f"HTTP {status}")
        except HTTPError as exc:
            return SendResult(
                ok=False,
                retryable=exc.code in {408, 429} or exc.code >= 500,
                error_message=f"HTTP {exc.code}",
                error_code=f"http_{exc.code}",
            )
        except Exception as exc:  # pragma: no cover
            return SendResult(
                ok=False,
                retryable=False,
                ambiguous=True,
                error_code="transport_unknown",
                error_message=f"HTTP transport error: {type(exc).__name__}",
            )
