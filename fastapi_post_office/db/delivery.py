"""Sync SQL primitives shared by sync and async repositories via run_sync."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from fastapi_post_office.backends.base import SendResult
from fastapi_post_office.exceptions import InvalidTransitionError

from .models import EmailAttempt, EmailMessage, EmailStatus


def finish_attempt(
    session: Session,
    message: EmailMessage,
    result: SendResult,
    next_attempt_at: datetime,
    duration_ms: int,
) -> None:
    now = datetime.now(timezone.utc)
    token = message.claim_token
    status = (
        EmailStatus.SENT
        if result.ok
        else (
            EmailStatus.SENDING
            if result.ambiguous
            else (
                EmailStatus.RETRYING
                if result.retryable and message.attempt_count < message.max_attempts
                else EmailStatus.FAILED
            )
        )
    )
    changed = session.execute(
        update(EmailMessage)
        .where(
            EmailMessage.id == message.id,
            EmailMessage.status == EmailStatus.SENDING,
            EmailMessage.claim_token == token,
        )
        .values(
            status=status,
            last_error_message=result.error_message,
            provider_message_id=result.provider_message_id,
            sent_at=now if result.ok else None,
            completed_at=now if status in {EmailStatus.SENT, EmailStatus.FAILED} else None,
            next_attempt_at=next_attempt_at if status == EmailStatus.RETRYING else None,
            claim_token=token if result.ambiguous else None,
        )
        .execution_options(synchronize_session=False)
    )
    if not getattr(changed, "rowcount", 0):
        session.rollback()
        raise InvalidTransitionError(
            "Claim no longer owned; delivery result requires reconciliation"
        )
    attempt = session.execute(
        select(EmailAttempt).where(EmailAttempt.claim_token == token)
    ).scalar_one()
    attempt.finished_at = now
    attempt.duration_ms = max(0, duration_ms)
    attempt.outcome = "UNKNOWN" if result.ambiguous else status.value
    attempt.error_code = result.error_code
    attempt.provider_message_id = result.provider_message_id
    session.commit()
    session.refresh(message)
