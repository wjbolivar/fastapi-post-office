from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi_post_office.config import Settings, settings
from fastapi_post_office.db.models import EmailMessage


@dataclass(frozen=True)
class EmailPayload:
    """Detached, immutable message snapshot passed to backends (safe across threads)."""

    id: UUID
    from_email: str
    to_json: tuple[str, ...]
    cc_json: tuple[str, ...]
    bcc_json: tuple[str, ...]
    subject: str
    html_body: str | None
    text_body: str | None
    idempotency_key: str | None

    @classmethod
    def from_message(cls, message: EmailMessage) -> EmailPayload:
        return cls(
            message.id,
            message.from_email,
            tuple(message.to_json),
            tuple(message.cc_json),
            tuple(message.bcc_json),
            message.subject,
            message.html_body,
            message.text_body,
            message.idempotency_key,
        )


@dataclass(frozen=True)
class SendResult:
    ok: bool
    provider_message_id: str | None = None
    error_message: str | None = None
    retryable: bool = True
    error_code: str | None = None
    ambiguous: bool = False


class EmailBackend:
    name: str = "base"

    def __init__(self, *, config: Settings | None = None) -> None:
        self.config = (config or settings).model_copy(deep=True)

    def send(self, message: EmailPayload) -> SendResult:
        raise NotImplementedError
