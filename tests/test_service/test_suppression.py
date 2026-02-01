from __future__ import annotations

import pytest

from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailTemplate, SuppressionReason
from fastapi_post_office.service import EmailService


def test_suppression_blocks_enqueue(repo):
    settings.block_suppressed = True
    repo.add_suppression("blocked@example.com", SuppressionReason.BOUNCE)
    repo.commit()

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
    with pytest.raises(ValueError):
        service.enqueue_template(
            template_name="welcome_user",
            to=["blocked@example.com"],
            context={},
            idempotency_key="k1",
        )
