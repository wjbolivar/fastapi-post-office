from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi_post_office.backends import get_backend
from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailMessage, EmailStatus, EmailTemplate
from fastapi_post_office.db.repository import EmailRepository
from fastapi_post_office.service.composer import compose_from_template
from fastapi_post_office.service.idempotency import ensure_idempotency
from fastapi_post_office.service.validator import (
    validate_from,
    validate_recipients,
    validate_subject,
)
from fastapi_post_office.templates.loader import TemplateSource
from fastapi_post_office.templates.manifest import TemplateManifest


class EmailService:
    def __init__(self, repo: EmailRepository) -> None:
        self.repo = repo
        self.backend = get_backend()

    def enqueue_template(
        self,
        template_name: str,
        to: Iterable[str],
        context: dict[str, Any],
        idempotency_key: str,
        cc: Iterable[str] | None = None,
        bcc: Iterable[str] | None = None,
        from_email: str | None = None,
    ) -> EmailMessage:
        existing = ensure_idempotency(self.repo, idempotency_key)
        if existing is not None:
            return existing

        template = self.repo.get_template(template_name, active_only=True)
        if template is None:
            raise ValueError(f"Template not found: {template_name}")

        source = _template_source_from_db(template)
        composed = compose_from_template(
            source,
            context=context,
            strict=settings.strict_template_vars,
            max_bytes=settings.max_template_bytes,
        )

        from_email_val = validate_from(from_email or settings.default_from)
        to_list = validate_recipients("to", to)
        cc_list = validate_recipients("cc", cc) if cc else []
        bcc_list = validate_recipients("bcc", bcc) if bcc else []

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
            max_attempts=settings.max_attempts,
            next_attempt_at=_next_attempt_at(0),
            idempotency_key=idempotency_key,
        )
        self.repo.create_message(message)
        self.repo.commit()
        return message

    def enqueue(
        self,
        to: Iterable[str],
        subject: str,
        html: str | None,
        text: str | None,
        idempotency_key: str,
        cc: Iterable[str] | None = None,
        bcc: Iterable[str] | None = None,
        from_email: str | None = None,
    ) -> EmailMessage:
        existing = ensure_idempotency(self.repo, idempotency_key)
        if existing is not None:
            return existing

        from_email_val = validate_from(from_email or settings.default_from)
        to_list = validate_recipients("to", to)
        cc_list = validate_recipients("cc", cc) if cc else []
        bcc_list = validate_recipients("bcc", bcc) if bcc else []

        if not html and not text:
            raise ValueError("Either html or text body is required")

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
            max_attempts=settings.max_attempts,
            next_attempt_at=_next_attempt_at(0),
            idempotency_key=idempotency_key,
        )
        self.repo.create_message(message)
        self.repo.commit()
        return message

    def send_now(self, message_id) -> EmailMessage:
        message = self.repo.get_message(message_id)
        if message is None:
            raise ValueError("Message not found")

        if message.status in {EmailStatus.SENT, EmailStatus.FAILED}:
            return message

        self.repo.set_status(message, EmailStatus.SENDING)
        self.repo.flush()

        result = self.backend.send(message)
        now = datetime.now(timezone.utc)

        self.repo.increment_attempt(message)
        if result.ok:
            self.repo.set_status(
                message,
                EmailStatus.SENT,
                provider_message_id=result.provider_message_id,
                sent_at=now,
                next_attempt_at=None,
            )
        else:
            if message.attempt_count >= message.max_attempts:
                self.repo.set_status(
                    message,
                    EmailStatus.FAILED,
                    error_message=result.error_message,
                    next_attempt_at=None,
                )
            else:
                self.repo.set_status(
                    message,
                    EmailStatus.RETRYING,
                    error_message=result.error_message,
                    next_attempt_at=_next_attempt_at(message.attempt_count),
                )

        self.repo.commit()
        return message


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


def _next_attempt_at(attempt_count: int) -> datetime:
    schedule = settings.retry_schedule_seconds
    index = min(attempt_count, len(schedule) - 1)
    delay = schedule[index]
    return datetime.now(timezone.utc) + timedelta(seconds=delay)
