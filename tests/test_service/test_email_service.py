from __future__ import annotations

import pytest

from fastapi_post_office.db.models import EmailTemplate
from fastapi_post_office.service import EmailService
from fastapi_post_office.service.idempotency import IdempotencyError


def test_enqueue_raw_requires_body(repo):
    service = EmailService(repo)
    with pytest.raises(ValueError):
        service.enqueue(
            to=["user@example.com"],
            subject="Hi",
            html=None,
            text=None,
            idempotency_key="k1",
        )


def test_enqueue_template_missing_template(repo):
    service = EmailService(repo)
    with pytest.raises(ValueError):
        service.enqueue_template(
            template_name="missing",
            to=["user@example.com"],
            context={},
            idempotency_key="k1",
        )


def test_idempotency_requires_key(repo):
    service = EmailService(repo)
    with pytest.raises(IdempotencyError):
        service.enqueue(
            to=["user@example.com"],
            subject="Hi",
            html="<b>Hi</b>",
            text=None,
            idempotency_key="",
        )


def test_send_now_success(repo):
    template = EmailTemplate(
        name="welcome_user",
        revision=1,
        subject_template="Hi",
        html_template=None,
        text_template="Hi",
        required_vars_json=[],
        content_policy_json=None,
        tags_json=[],
        source_hash="hash",
        is_active=True,
    )
    repo.upsert_template(template)
    repo.commit()

    service = EmailService(repo)
    msg = service.enqueue_template(
        template_name="welcome_user",
        to=["user@example.com"],
        context={},
        idempotency_key="k1",
    )

    sent = service.send_now(msg.id)
    assert sent.status.name == "SENT"
