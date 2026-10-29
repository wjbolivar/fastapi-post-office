from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import and_, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .delivery import finish_attempt as _finish_attempt
from .models import (
    EmailAttempt,
    EmailMessage,
    EmailStatus,
    EmailSuppression,
    EmailTemplate,
    SuppressionReason,
)
from .transactions import ensure_outer_transaction


class EmailRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_template(self, name: str, active_only: bool = True) -> EmailTemplate | None:
        stmt = select(EmailTemplate).where(EmailTemplate.name == name)
        if active_only:
            stmt = stmt.where(EmailTemplate.is_active.is_(True))
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert_template(self, template: EmailTemplate) -> EmailTemplate:
        existing = self.get_template(template.name, active_only=False)
        if existing is None:
            self.session.add(template)
            return template
        existing.revision = template.revision
        existing.subject_template = template.subject_template
        existing.html_template = template.html_template
        existing.text_template = template.text_template
        existing.required_vars_json = template.required_vars_json
        existing.content_policy_json = template.content_policy_json
        existing.tags_json = template.tags_json
        existing.source_hash = template.source_hash
        existing.is_active = template.is_active
        return existing

    def create_message(self, message: EmailMessage) -> EmailMessage:
        if message.idempotency_key is None:
            self.session.add(message)
            return message
        # Flush caller-owned changes outside the email savepoint error handler.
        self.session.flush()
        ensure_outer_transaction(self.session)
        try:
            with self.session.begin_nested():
                self.session.add(message)
                self.session.flush()
        except IntegrityError:
            existing = self.get_message_by_idempotency(message.idempotency_key)
            if existing is None:
                raise
            return existing
        return message

    def get_message(self, message_id) -> EmailMessage | None:
        return self.session.get(EmailMessage, message_id)

    def claim_message(self, message_id) -> bool:
        """Atomically claim a due message; commit before contacting the provider.

        A crashed worker leaves SENDING for explicit operator reconciliation.
        Automatically retrying that state could duplicate an accepted email.
        """
        now = datetime.now(timezone.utc)
        token = uuid.uuid4()
        stmt = (
            update(EmailMessage)
            .where(
                EmailMessage.id == message_id,
                EmailMessage.status.in_([EmailStatus.QUEUED, EmailStatus.RETRYING]),
                EmailMessage.attempt_count < EmailMessage.max_attempts,
                (EmailMessage.next_attempt_at.is_(None)) | (EmailMessage.next_attempt_at <= now),
            )
            .values(
                status=EmailStatus.SENDING,
                sending_started_at=now,
                completed_at=None,
                claim_token=token,
                attempt_count=EmailMessage.attempt_count + 1,
                next_attempt_at=None,
            )
            .execution_options(synchronize_session=False)
        )
        result = self.session.execute(stmt)
        claimed = bool(getattr(result, "rowcount", 0))
        if claimed:
            message = self.session.get(EmailMessage, message_id, populate_existing=True)
            if message is None:
                raise RuntimeError("Claimed message disappeared")
            self.session.add(
                EmailAttempt(
                    message_id=message_id,
                    number=message.attempt_count,
                    claim_token=token,
                    provider=message.provider,
                    started_at=now,
                    outcome="STARTED",
                )
            )
        self.session.commit()
        return claimed

    def finish_attempt(self, message, result, next_attempt_at, duration_ms) -> None:
        _finish_attempt(self.session, message, result, next_attempt_at, duration_ms)

    def get_message_by_idempotency(self, key: str) -> EmailMessage | None:
        stmt = select(EmailMessage).where(EmailMessage.idempotency_key == key)
        return self.session.execute(stmt).scalar_one_or_none()

    def is_suppressed(self, email: str) -> bool:
        stmt = select(EmailSuppression).where(EmailSuppression.email == email.lower())
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def add_suppression(
        self,
        email: str,
        reason: SuppressionReason,
        provider: str | None = None,
        metadata: dict | None = None,
    ) -> EmailSuppression:
        suppression = EmailSuppression(
            email=email.lower(),
            reason=reason,
            provider=provider,
            metadata_json=metadata,
        )
        self.session.add(suppression)
        return suppression

    def remove_suppression(self, email: str) -> None:
        stmt = delete(EmailSuppression).where(EmailSuppression.email == email.lower())
        self.session.execute(stmt)

    def set_status(
        self,
        message: EmailMessage,
        status: EmailStatus,
        error_message: str | None = None,
        provider_message_id: str | None = None,
        sent_at: datetime | None = None,
        next_attempt_at: datetime | None = None,
    ) -> EmailMessage:
        message.status = status
        message.last_error_message = error_message
        message.provider_message_id = provider_message_id
        message.sent_at = sent_at
        message.next_attempt_at = next_attempt_at
        return message

    def increment_attempt(self, message: EmailMessage) -> EmailMessage:
        message.attempt_count += 1
        return message

    def list_due_messages(
        self, now: datetime | None = None, limit: int = 100
    ) -> list[EmailMessage]:
        if limit < 1:
            raise ValueError("limit must be positive")
        if now is None:
            now = datetime.now(timezone.utc)
        stmt = select(EmailMessage).where(
            and_(
                EmailMessage.status.in_([EmailStatus.QUEUED, EmailStatus.RETRYING]),
                EmailMessage.next_attempt_at.is_not(None),
                EmailMessage.next_attempt_at <= now,
            )
        )
        stmt = stmt.order_by(EmailMessage.next_attempt_at, EmailMessage.id).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def cleanup_sent(self, retention_days: int) -> int:
        from fastapi_post_office.queue import QueueManager

        return QueueManager(self.session).cleanup(retention_days=retention_days, dry_run=False)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def flush(self) -> None:
        self.session.flush()

    def bulk_add(self, items: Iterable[object]) -> None:
        self.session.add_all(list(items))
