from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Integer, String, Text, func
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


def _json_type() -> Any:
    # Prefer JSONB on Postgres, fallback to generic JSON elsewhere.
    return JSONB().with_variant(JSON(), "sqlite")


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4, primary_key=True, unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_template: Mapped[str] = mapped_column(Text, nullable=False)
    html_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required_vars_json: Mapped[list[str]] = mapped_column(_json_type(), nullable=False)
    content_policy_json: Mapped[Optional[dict[str, Any]]] = mapped_column(_json_type(), nullable=True)
    tags_json: Mapped[list[str]] = mapped_column(_json_type(), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4, primary_key=True, unique=True, nullable=False
    )
    template_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    template_revision_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[EmailStatus] = mapped_column(
        SAEnum(EmailStatus, name="email_status"), default=EmailStatus.QUEUED, nullable=False
    )
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    to_json: Mapped[list[str]] = mapped_column(_json_type(), nullable=False)
    cc_json: Mapped[list[str]] = mapped_column(_json_type(), nullable=False)
    bcc_json: Mapped[list[str]] = mapped_column(_json_type(), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    html_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
