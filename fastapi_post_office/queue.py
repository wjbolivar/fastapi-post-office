"""Operator APIs. Mutations commit: use a dedicated session for queue management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from .db.models import EmailAttempt, EmailEvent, EmailMessage, EmailStatus
from .db.transactions import ensure_outer_transaction
from .exceptions import (
    InvalidTransitionError,
    MessageNotFoundError,
    TransactionModeError,
    ValidationError,
)


def _utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class QueueManager:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_messages(
        self, *, status: EmailStatus | None = None, older_than_seconds: int = 0, limit: int = 100
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000 or older_than_seconds < 0:
            raise ValidationError("limit must be 1..1000 and age non-negative")
        stmt = select(EmailMessage).order_by(EmailMessage.created_at, EmailMessage.id).limit(limit)
        if status is not None:
            stmt = stmt.where(EmailMessage.status == status)
        if older_than_seconds:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
            stmt = stmt.where(
                func.coalesce(EmailMessage.sending_started_at, EmailMessage.created_at) <= cutoff
            )
        return [self._summary(m) for m in self.session.scalars(stmt)]

    @staticmethod
    def _summary(message: EmailMessage) -> dict[str, Any]:
        return {
            "id": str(message.id),
            "status": message.status.value,
            "attempt_count": message.attempt_count,
            "max_attempts": message.max_attempts,
            "provider": message.provider,
            "next_attempt_at": (
                message.next_attempt_at.isoformat() if message.next_attempt_at else None
            ),
            "sending_started_at": (
                message.sending_started_at.isoformat() if message.sending_started_at else None
            ),
            "provider_message_id": message.provider_message_id,
        }

    def inspect(self, message_id: UUID) -> dict[str, Any]:
        message = self.session.get(EmailMessage, message_id, populate_existing=True)
        if message is None:
            raise MessageNotFoundError("Message not found")
        data = self._summary(message)
        data["attempts"] = [
            {
                "number": a.number,
                "outcome": a.outcome,
                "provider": a.provider,
                "started_at": a.started_at.isoformat(),
                "finished_at": a.finished_at.isoformat() if a.finished_at else None,
                "duration_ms": a.duration_ms,
                "error_code": a.error_code,
                "provider_message_id": a.provider_message_id,
            }
            for a in self.session.scalars(
                select(EmailAttempt)
                .where(EmailAttempt.message_id == message_id)
                .order_by(EmailAttempt.number)
            )
        ]
        data["events"] = [
            {
                "action": e.action,
                "actor": e.actor,
                "note": e.note,
                "created_at": e.created_at.isoformat(),
            }
            for e in self.session.scalars(
                select(EmailEvent)
                .where(EmailEvent.message_id == message_id)
                .order_by(EmailEvent.created_at, EmailEvent.id)
            )
        ]
        return data

    def _clean_session(self) -> None:
        if self.session.new or self.session.dirty or self.session.deleted:
            raise TransactionModeError("Queue operations require a session without pending changes")

    def transition(
        self,
        message_id: UUID,
        *,
        action: str,
        expected_attempt: int,
        actor: str,
        note: str,
        acknowledge_duplicate_risk: bool = False,
        additional_attempts: int = 3,
        provider_message_id: str | None = None,
    ) -> dict[str, Any]:
        """CAS transition; reconciliation requires the worker to be stopped first."""
        self._clean_session()
        if not actor.strip() or not note.strip() or len(actor) > 255 or len(note) > 1000:
            raise ValidationError("actor and note are required (max 255/1000 characters)")
        if expected_attempt < 0 or additional_attempts < 1:
            raise ValidationError("Invalid attempt count")
        if provider_message_id and len(provider_message_id) > 255:
            raise ValidationError("Provider identifier exceeds 255 characters")
        message = self.session.get(EmailMessage, message_id, populate_existing=True)
        if message is None:
            raise MessageNotFoundError("Message not found")
        before = message.status
        if action == "cancel" and before in {EmailStatus.QUEUED, EmailStatus.RETRYING}:
            target = EmailStatus.CANCELLED
        elif action == "retry" and before == EmailStatus.FAILED:
            if not acknowledge_duplicate_risk:
                raise InvalidTransitionError(
                    "Retry requires explicit duplicate-risk acknowledgement"
                )
            target = EmailStatus.QUEUED
        elif (
            action in {"reconcile-sent", "reconcile-failed", "reconcile-retry"}
            and before == EmailStatus.SENDING
        ):
            if not acknowledge_duplicate_risk:
                raise InvalidTransitionError(
                    "Stop the worker and acknowledge delivery ambiguity before reconciliation"
                )
            target = {
                "reconcile-sent": EmailStatus.SENT,
                "reconcile-failed": EmailStatus.FAILED,
                "reconcile-retry": EmailStatus.QUEUED,
            }[action]
        else:
            raise InvalidTransitionError(f"Cannot {action} a message in {before.value}")
        now = datetime.now(timezone.utc)
        changed = self.session.execute(
            update(EmailMessage)
            .where(
                EmailMessage.id == message_id,
                EmailMessage.status == before,
                EmailMessage.attempt_count == expected_attempt,
                EmailMessage.claim_token == message.claim_token,
            )
            .values(
                status=target,
                claim_token=None,
                next_attempt_at=now if target == EmailStatus.QUEUED else None,
                completed_at=None if target == EmailStatus.QUEUED else now,
                sent_at=now if target == EmailStatus.SENT else None,
                provider_message_id=provider_message_id,
                last_error_message=None,
                max_attempts=(
                    message.attempt_count + additional_attempts
                    if target == EmailStatus.QUEUED
                    else message.max_attempts
                ),
            )
            .execution_options(synchronize_session=False)
        )
        if not getattr(changed, "rowcount", 0):
            self.session.rollback()
            raise InvalidTransitionError(
                "Message changed; inspect it again before retrying the operation"
            )
        if before == EmailStatus.SENDING:
            self.session.execute(
                update(EmailAttempt)
                .where(EmailAttempt.claim_token == message.claim_token)
                .values(
                    outcome="RECONCILED_SENT" if target == EmailStatus.SENT else "UNKNOWN",
                    finished_at=now,
                )
            )
        self.session.add(EmailEvent(message_id=message_id, action=action, actor=actor, note=note))
        self.session.commit()
        return self.inspect(message_id)

    def cleanup(
        self, *, retention_days: int, include_failed: bool = False, dry_run: bool = True
    ) -> int:
        self._clean_session()
        if retention_days < 0:
            raise ValidationError("retention_days must be non-negative")
        statuses = [EmailStatus.SENT, EmailStatus.CANCELLED]
        if include_failed:
            statuses.append(EmailStatus.FAILED)
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        # Old FAILED rows without completed_at are deliberately preserved for reconciliation.
        eligible = select(EmailMessage.id).where(
            EmailMessage.status.in_(statuses),
            func.coalesce(EmailMessage.completed_at, EmailMessage.sent_at) <= cutoff,
        )
        count = self.session.scalar(select(func.count()).select_from(eligible.subquery())) or 0
        if not dry_run:
            ensure_outer_transaction(self.session, immediate=True)
            # Lock terminal parents before deleting history, so a concurrent retry cannot
            # keep the parent while losing its attempts. Bound each deletion transaction.
            ids = list(self.session.scalars(eligible.limit(1000).with_for_update(skip_locked=True)))
            if not ids:
                return 0
            eligible = select(EmailMessage.id).where(EmailMessage.id.in_(ids))
            count = len(ids)
            # Explicit child cleanup also works with SQLite foreign keys disabled.
            self.session.execute(delete(EmailAttempt).where(EmailAttempt.message_id.in_(eligible)))
            self.session.execute(delete(EmailEvent).where(EmailEvent.message_id.in_(eligible)))
            self.session.execute(delete(EmailMessage).where(EmailMessage.id.in_(eligible)))
            self.session.commit()
        return count

    def metrics(self, *, stuck_after_seconds: int = 300) -> dict[str, Any]:
        if stuck_after_seconds < 1:
            raise ValidationError("stuck_after_seconds must be positive")
        now = datetime.now(timezone.utc)
        counts = {s.value: 0 for s in EmailStatus}
        counts.update(
            {
                status.value: count
                for status, count in self.session.execute(
                    select(EmailMessage.status, func.count()).group_by(EmailMessage.status)
                )
            }
        )
        due = (
            EmailMessage.status.in_([EmailStatus.QUEUED, EmailStatus.RETRYING]),
            EmailMessage.next_attempt_at <= now,
        )
        oldest = self.session.scalar(select(func.min(EmailMessage.next_attempt_at)).where(*due))
        durations = self.session.execute(
            select(func.count(EmailAttempt.id), func.avg(EmailAttempt.duration_ms))
        ).one()
        return {
            "counts": counts,
            "due": self.session.scalar(select(func.count()).select_from(EmailMessage).where(*due))
            or 0,
            "oldest_due_age_seconds": (
                max(0.0, (now - _utc(oldest)).total_seconds()) if oldest else 0.0
            ),
            "stuck": self.session.scalar(
                select(func.count())
                .select_from(EmailMessage)
                .where(
                    EmailMessage.status == EmailStatus.SENDING,
                    func.coalesce(EmailMessage.sending_started_at, EmailMessage.created_at)
                    <= now - timedelta(seconds=stuck_after_seconds),
                )
            )
            or 0,
            "attempts": durations[0],
            "average_attempt_duration_ms": float(durations[1] or 0),
        }


class AsyncQueueManager:
    """Same API as QueueManager on an AsyncSession, without blocking database I/O."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_messages(self, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.session.run_sync(lambda s: QueueManager(s).list_messages(**kwargs))

    async def inspect(self, message_id: UUID) -> dict[str, Any]:
        return await self.session.run_sync(lambda s: QueueManager(s).inspect(message_id))

    async def transition(self, message_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return await self.session.run_sync(
            lambda s: QueueManager(s).transition(message_id, **kwargs)
        )

    async def cleanup(self, **kwargs: Any) -> int:
        return await self.session.run_sync(lambda s: QueueManager(s).cleanup(**kwargs))

    async def metrics(self, **kwargs: Any) -> dict[str, Any]:
        return await self.session.run_sync(lambda s: QueueManager(s).metrics(**kwargs))
