from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import and_, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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


class AsyncEmailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_template(self, name: str, active_only: bool = True) -> EmailTemplate | None:
        stmt = select(EmailTemplate).where(EmailTemplate.name == name)
        if active_only:
            stmt = stmt.where(EmailTemplate.is_active.is_(True))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_template(self, template: EmailTemplate) -> EmailTemplate:
        existing = await self.get_template(template.name, active_only=False)
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

    async def create_message(self, message: EmailMessage) -> EmailMessage:
        if message.idempotency_key is None:
            self.session.add(message)
            return message
        # Flush caller-owned changes outside the email savepoint error handler.
        await self.session.flush()
        await self.session.run_sync(ensure_outer_transaction)
        try:
            async with self.session.begin_nested():
                self.session.add(message)
                await self.session.flush()
        except IntegrityError:
            existing = await self.get_message_by_idempotency(message.idempotency_key)
            if existing is None:
                raise
            return existing
        return message

    async def get_message(self, message_id) -> EmailMessage | None:
        return await self.session.get(EmailMessage, message_id)

    async def claim_message(self, message_id) -> bool:
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
        result = await self.session.execute(stmt)
        claimed = bool(getattr(result, "rowcount", 0))
        if claimed:
            message = await self.session.get(EmailMessage, message_id, populate_existing=True)
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
        await self.session.commit()
        return claimed

    async def finish_attempt(self, message, result, next_attempt_at, duration_ms) -> None:
        await self.session.run_sync(_finish_attempt, message, result, next_attempt_at, duration_ms)

    async def get_message_by_idempotency(self, key: str) -> EmailMessage | None:
        stmt = select(EmailMessage).where(EmailMessage.idempotency_key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_status(
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

    async def increment_attempt(self, message: EmailMessage) -> EmailMessage:
        message.attempt_count += 1
        return message

    async def list_due_messages(
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
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def cleanup_sent(self, retention_days: int) -> int:
        from fastapi_post_office.queue import QueueManager

        return await self.session.run_sync(
            lambda session: QueueManager(session).cleanup(
                retention_days=retention_days, dry_run=False
            )
        )

    async def is_suppressed(self, email: str) -> bool:
        stmt = select(EmailSuppression).where(EmailSuppression.email == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add_suppression(
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

    async def remove_suppression(self, email: str) -> None:
        stmt = delete(EmailSuppression).where(EmailSuppression.email == email.lower())
        await self.session.execute(stmt)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def flush(self) -> None:
        await self.session.flush()

    async def bulk_add(self, items: Iterable[object]) -> None:
        self.session.add_all(list(items))
