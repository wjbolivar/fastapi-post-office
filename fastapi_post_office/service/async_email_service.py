from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any

from fastapi_post_office.backends import get_backend
from fastapi_post_office.backends.base import EmailBackend, EmailPayload, SendResult
from fastapi_post_office.config import Settings, settings
from fastapi_post_office.db.async_repository import AsyncEmailRepository
from fastapi_post_office.db.models import EmailMessage, EmailStatus, EmailTemplate
from fastapi_post_office.exceptions import (
    MessageNotFoundError,
    SuppressedRecipientError,
    TemplateNotFoundError,
    TransactionModeError,
    ValidationError,
)
from fastapi_post_office.service.composer import compose_from_template
from fastapi_post_office.service.idempotency import (
    ensure_idempotency_async,
    normalize_idempotency_key,
)
from fastapi_post_office.service.validator import (
    validate_from,
    validate_recipients,
    validate_subject,
)
from fastapi_post_office.templates.loader import TemplateSource
from fastapi_post_office.templates.manifest import TemplateManifest


class AsyncEmailService:
    def __init__(
        self,
        repo: AsyncEmailRepository,
        *,
        config: Settings | None = None,
        backend: EmailBackend | None = None,
        auto_commit: bool = True,
    ) -> None:
        self.repo = repo
        self.config = (config or settings).model_copy(deep=True)
        self.backend = backend if backend is not None else get_backend(config=self.config)
        self.auto_commit = auto_commit

    async def enqueue_template(
        self,
        template_name: str,
        to: Iterable[str],
        context: dict[str, Any],
        idempotency_key: str,
        cc: Iterable[str] | None = None,
        bcc: Iterable[str] | None = None,
        from_email: str | None = None,
    ) -> EmailMessage:
        idempotency_key = normalize_idempotency_key(idempotency_key)
        existing = await ensure_idempotency_async(self.repo, idempotency_key)
        if existing is not None:
            return _ensure_message(existing)

        template = await self.repo.get_template(template_name, active_only=True)
        if template is None:
            raise TemplateNotFoundError(f"Template not found: {template_name}")

        source = _template_source_from_db(template)
        composed = compose_from_template(
            source,
            context=context,
            strict=self.config.strict_template_vars,
            max_bytes=self.config.max_template_bytes,
        )

        from_email_val = validate_from(from_email or self.config.default_from)
        to_list = validate_recipients("to", to)
        cc_list = validate_recipients("cc", cc) if cc else []
        bcc_list = validate_recipients("bcc", bcc) if bcc else []
        await self._ensure_not_suppressed(to_list + cc_list + bcc_list)

        message = EmailMessage(
            template_name=composed.template_name,
            template_revision_used=composed.template_revision,
            provider=self.backend.name,
            status=EmailStatus.QUEUED,
            from_email=from_email_val,
            to_json=to_list,
            cc_json=cc_list,
            bcc_json=bcc_list,
            subject=validate_subject(composed.subject),
            html_body=composed.html_body,
            text_body=composed.text_body,
            attempt_count=0,
            max_attempts=self.config.max_attempts,
            next_attempt_at=self._next_attempt_at(0),
            idempotency_key=idempotency_key,
        )
        message = await self.repo.create_message(message)
        if self.auto_commit:
            await self.repo.commit()
        else:
            await self.repo.flush()
        return message

    async def enqueue(
        self,
        to: Iterable[str],
        subject: str,
        html: str | None = None,
        text: str | None = None,
        idempotency_key: str = "",
        cc: Iterable[str] | None = None,
        bcc: Iterable[str] | None = None,
        from_email: str | None = None,
    ) -> EmailMessage:
        idempotency_key = normalize_idempotency_key(idempotency_key)
        existing = await ensure_idempotency_async(self.repo, idempotency_key)
        if existing is not None:
            return _ensure_message(existing)

        from_email_val = validate_from(from_email or self.config.default_from)
        to_list = validate_recipients("to", to)
        cc_list = validate_recipients("cc", cc) if cc else []
        bcc_list = validate_recipients("bcc", bcc) if bcc else []
        await self._ensure_not_suppressed(to_list + cc_list + bcc_list)

        if not html and not text:
            raise ValidationError("Either html or text body is required")

        message = EmailMessage(
            template_name=None,
            template_revision_used=None,
            provider=self.backend.name,
            status=EmailStatus.QUEUED,
            from_email=from_email_val,
            to_json=to_list,
            cc_json=cc_list,
            bcc_json=bcc_list,
            subject=validate_subject(subject),
            html_body=html,
            text_body=text,
            attempt_count=0,
            max_attempts=self.config.max_attempts,
            next_attempt_at=self._next_attempt_at(0),
            idempotency_key=idempotency_key,
        )
        message = await self.repo.create_message(message)
        if self.auto_commit:
            await self.repo.commit()
        else:
            await self.repo.flush()
        return message

    async def send_now(self, message_id) -> EmailMessage:
        """Send using a dedicated session; never use this inside a business transaction."""
        if not self.auto_commit:
            raise TransactionModeError("send_now requires auto_commit=True and a dedicated session")
        session = self.repo.session
        if session.new or session.dirty or session.deleted:
            raise TransactionModeError("send_now requires a session without pending changes")
        claimed = await self.repo.claim_message(message_id)
        message = await self.repo.get_message(message_id)
        if message is None:
            raise MessageNotFoundError("Message not found")
        await session.refresh(message)
        if not claimed:
            return message

        started = perf_counter()
        try:
            await self._ensure_not_suppressed(message.to_json + message.cc_json + message.bcc_json)
        except SuppressedRecipientError:
            result = SendResult(
                ok=False,
                retryable=False,
                error_message="Recipient suppressed",
                error_code="suppressed",
            )
        else:
            try:
                backend = self.backend
                if message.provider and message.provider != backend.name:
                    backend = get_backend(message.provider, config=self.config)
                result = await asyncio.to_thread(backend.send, EmailPayload.from_message(message))
            except Exception as exc:
                result = SendResult(
                    ok=False,
                    error_message=f"Backend error: {type(exc).__name__}",
                    error_code="backend_exception",
                    retryable=False,
                    ambiguous=True,
                )
        await self.repo.finish_attempt(
            message,
            result,
            self._next_attempt_at(message.attempt_count),
            int((perf_counter() - started) * 1000),
        )
        return message

    async def _ensure_not_suppressed(self, recipients: list[str]) -> None:
        if not self.config.block_suppressed:
            return
        for email in recipients:
            if await self.repo.is_suppressed(email):
                raise SuppressedRecipientError(f"Recipient suppressed: {email}")

    def _next_attempt_at(self, attempt_count: int) -> datetime:
        schedule = self.config.retry_schedule_seconds
        index = min(attempt_count, len(schedule) - 1)
        delay = schedule[index]
        return datetime.now(timezone.utc) + timedelta(seconds=delay)


def _template_source_from_db(template: EmailTemplate) -> TemplateSource:
    manifest = TemplateManifest(
        name=template.name,
        revision=template.revision,
        description="",
        required_vars=template.required_vars_json,
        tags=template.tags_json,
        content_policy=template.content_policy_json,
    )
    return TemplateSource(
        manifest=manifest,
        subject_template=template.subject_template,
        html_template=template.html_template,
        text_template=template.text_template,
        source_hash=template.source_hash,
    )


def _ensure_message(message: Any) -> EmailMessage:
    if not isinstance(message, EmailMessage):
        raise TypeError("Idempotency lookup returned invalid message type")
    return message
