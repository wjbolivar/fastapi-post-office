from __future__ import annotations

from fastapi_post_office.backends.console import ConsoleBackend
from fastapi_post_office.db.models import EmailMessage


def test_console_backend_send():
    backend = ConsoleBackend()
    message = EmailMessage(
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
    result = backend.send(message)
    assert result.ok is True
