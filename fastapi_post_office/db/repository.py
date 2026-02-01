from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from .models import EmailMessage, EmailStatus, EmailTemplate


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
        self.session.add(message)
        return message

    def get_message(self, message_id) -> EmailMessage | None:
        return self.session.get(EmailMessage, message_id)

    def get_message_by_idempotency(self, key: str) -> EmailMessage | None:
        stmt = select(EmailMessage).where(EmailMessage.idempotency_key == key)
        return self.session.execute(stmt).scalar_one_or_none()

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

    def list_due_messages(self, now: datetime | None = None) -> list[EmailMessage]:
        if now is None:
            now = datetime.now(timezone.utc)
        stmt = select(EmailMessage).where(
            and_(
                EmailMessage.status.in_([EmailStatus.QUEUED, EmailStatus.RETRYING]),
                EmailMessage.next_attempt_at.is_not(None),
                EmailMessage.next_attempt_at <= now,
            )
        )
        return list(self.session.execute(stmt).scalars().all())

    def cleanup_sent(self, retention_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt = delete(EmailMessage).where(
            and_(EmailMessage.status == EmailStatus.SENT, EmailMessage.sent_at <= cutoff)
        )
        result = self.session.execute(stmt)
        rowcount = getattr(result, "rowcount", None)
        return int(rowcount or 0)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def flush(self) -> None:
        self.session.flush()

    def bulk_add(self, items: Iterable[object]) -> None:
        self.session.add_all(list(items))
