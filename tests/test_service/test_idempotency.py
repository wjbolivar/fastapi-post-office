from __future__ import annotations

from fastapi_post_office.db.models import EmailTemplate
from fastapi_post_office.service import EmailService


def test_idempotency_returns_existing(repo):
    template = EmailTemplate(
        name="welcome_user",
        revision=1,
        subject_template="Hi {{ first_name }}",
        html_template="<b>Hi {{ first_name }}</b>",
        text_template="Hi {{ first_name }}",
        required_vars_json=["first_name"],
        content_policy_json=None,
        tags_json=[],
        source_hash="hash",
        is_active=True,
    )
    repo.upsert_template(template)
    repo.commit()

    service = EmailService(repo)
    msg1 = service.enqueue_template(
        template_name="welcome_user",
        to=["user@example.com"],
        context={"first_name": "Ana"},
        idempotency_key="k1",
    )
    msg2 = service.enqueue_template(
        template_name="welcome_user",
        to=["user@example.com"],
        context={"first_name": "Ana"},
        idempotency_key="k1",
    )
    assert msg1.id == msg2.id
