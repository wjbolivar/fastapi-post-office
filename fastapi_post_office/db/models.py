from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .base import Base


class EmailStatus(str, Enum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    RETRYING = "RETRYING"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def _json_type() -> Any:
    # Prefer JSONB on Postgres, fallback to generic JSON elsewhere.
    return JSON().with_variant(JSONB(), "postgresql")


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4, primary_key=True, unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_template: Mapped[str] = mapped_column(Text, nullable=False)
    html_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_vars_json: Mapped[list[str]] = mapped_column(_json_type(), nullable=False)
    content_policy_json: Mapped[dict[str, Any] | None] = mapped_column(_json_type(), nullable=True)
    tags_json: Mapped[list[str]] = mapped_column(_json_type(), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (Index("ix_email_messages_due", "status", "next_attempt_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4, primary_key=True, unique=True, nullable=False
    )
    template_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    template_revision_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[EmailStatus] = mapped_column(
        SAEnum(EmailStatus, name="email_status"), default=EmailStatus.QUEUED, nullable=False
    )
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    to_json: Mapped[list[str]] = mapped_column(_json_type(), nullable=False)
    cc_json: Mapped[list[str]] = mapped_column(_json_type(), nullable=False)
    bcc_json: Mapped[list[str]] = mapped_column(_json_type(), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sending_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_token: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SuppressionReason(str, Enum):
    BOUNCE = "BOUNCE"
    COMPLAINT = "COMPLAINT"
    MANUAL = "MANUAL"


class EmailSuppression(Base):
    __tablename__ = "email_suppressions"

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4, primary_key=True, unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    reason: Mapped[SuppressionReason] = mapped_column(
        SAEnum(SuppressionReason, name="suppression_reason"),
        default=SuppressionReason.MANUAL,
        nullable=False,
    )
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(_json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailAttempt(Base):
    __tablename__ = "email_attempts"
    __table_args__ = (UniqueConstraint("message_id", "number", name="uq_email_attempt_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    claim_token: Mapped[uuid.UUID] = mapped_column(unique=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), default="STARTED")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class EmailEvent(Base):
    __tablename__ = "email_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(255))
    note: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
