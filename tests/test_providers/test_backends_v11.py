from __future__ import annotations

import pytest

from fastapi_post_office.backends.postmark import PostmarkBackend
from fastapi_post_office.backends.sendgrid import SendGridBackend
from fastapi_post_office.backends.sendpulse import SendPulseBackend
from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailMessage


def _message() -> EmailMessage:
    return EmailMessage(
        from_email="no-reply@example.com",
        to_json=["user@example.com"],
        cc_json=[],
        bcc_json=[],
        subject="Hello",
        html_body="<b>Hi</b>",
        text_body="Hi",
        attempt_count=0,
        max_attempts=3,
    )


def test_sendgrid_requires_key():
    settings.sendgrid_api_key = None
    backend = SendGridBackend()
    with pytest.raises(RuntimeError):
        backend.build_headers()


def test_postmark_requires_token():
    settings.postmark_server_token = None
    backend = PostmarkBackend()
    with pytest.raises(RuntimeError):
        backend.build_headers()


def test_sendpulse_requires_token():
    settings.sendpulse_api_token = None
    backend = SendPulseBackend()
    with pytest.raises(RuntimeError):
        backend.build_headers()
