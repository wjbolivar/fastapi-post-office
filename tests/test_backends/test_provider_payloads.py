from __future__ import annotations

from fastapi_post_office.backends.postmark import PostmarkBackend
from fastapi_post_office.backends.sendgrid import SendGridBackend
from fastapi_post_office.backends.sendpulse import SendPulseBackend
from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailMessage


def _message() -> EmailMessage:
    return EmailMessage(
        from_email="no-reply@example.com",
        to_json=["user@example.com"],
        cc_json=["cc@example.com"],
        bcc_json=["bcc@example.com"],
        subject="Hello",
        html_body="<b>Hi</b>",
        text_body="Hi",
        attempt_count=0,
        max_attempts=3,
    )


def test_sendgrid_payload():
    backend = SendGridBackend()
    payload = backend.build_payload(_message())
    assert payload["personalizations"]
    assert payload["content"]


def test_postmark_payload():
    backend = PostmarkBackend()
    payload = backend.build_payload(_message())
    assert payload["To"]
    assert payload["Subject"]


def test_sendpulse_payload():
    settings.sendpulse_from_name = "FAPO"
    backend = SendPulseBackend()
    payload = backend.build_payload(_message())
    assert payload["email"]["subject"] == "Hello"
