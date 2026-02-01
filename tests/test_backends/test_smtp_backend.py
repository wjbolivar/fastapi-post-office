from __future__ import annotations

from fastapi_post_office.backends.smtp import SMTPBackend
from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailMessage


class DummySMTP:
    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started = False
        self.logged_in = False
        self.sent = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        self.started = True

    def login(self, user, password):
        self.logged_in = True

    def send_message(self, msg):
        self.sent = True


def test_smtp_backend_send(monkeypatch):
    settings.smtp_host = "localhost"
    settings.smtp_port = 1025
    settings.smtp_username = "user"
    settings.smtp_password = "pass"
    settings.smtp_starttls = True

    monkeypatch.setattr("smtplib.SMTP", DummySMTP)

    backend = SMTPBackend()
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
