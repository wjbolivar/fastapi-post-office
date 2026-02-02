from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EmailMessage, EmailStatus, EmailSuppression, EmailTemplate, SuppressionReason


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
        self.session.add(message)
        return message

    async def get_message(self, message_id) -> EmailMessage | None:
        return await self.session.get(EmailMessage, message_id)

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

    async def list_due_messages(self, now: datetime | None = None) -> list[EmailMessage]:
        if now is None:
            now = datetime.now(timezone.utc)
        stmt = select(EmailMessage).where(
            and_(
                EmailMessage.status.in_([EmailStatus.QUEUED, EmailStatus.RETRYING]),
                EmailMessage.next_attempt_at.is_not(None),
                EmailMessage.next_attempt_at <= now,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def cleanup_sent(self, retention_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt = delete(EmailMessage).where(
            and_(EmailMessage.status == EmailStatus.SENT, EmailMessage.sent_at <= cutoff)
        )
        result = await self.session.execute(stmt)
        rowcount = getattr(result, "rowcount", None)
        return int(rowcount or 0)

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
