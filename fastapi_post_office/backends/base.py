from __future__ import annotations

from dataclasses import dataclass

from fastapi_post_office.db.models import EmailMessage


@dataclass(frozen=True)
class SendResult:
    ok: bool
    provider_message_id: str | None = None
    error_message: str | None = None


class EmailBackend:
    name: str = "base"

    def send(self, message: EmailMessage) -> SendResult:
        raise NotImplementedError
