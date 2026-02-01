from __future__ import annotations

import pytest

from fastapi_post_office.backends.ses import SESBackend
from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailMessage


def test_ses_requires_smtp_host():
    settings.smtp_host = None
    backend = SESBackend()
    message = EmailMessage(
        from_email="no-reply@example.com",
        to_json=["user@example.com"],
        cc_json=[],
        bcc_json=[],
        subject="Hello",
        html_body=None,
        text_body="Hi",
        attempt_count=0,
        max_attempts=3,
    )
    with pytest.raises(RuntimeError):
        backend.send(message)
