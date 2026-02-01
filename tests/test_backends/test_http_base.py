from __future__ import annotations

from fastapi_post_office.backends.http_base import HttpApiBackend
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


def test_http_backend_missing_url():
    backend = HttpApiBackend()
    result = backend.send(_message())
    assert result.ok is False


def test_http_backend_success(monkeypatch):
    class Dummy(HttpApiBackend):
        api_url = "https://example.test/send"

        def build_payload(self, message):
            return {"subject": message.subject}

    class DummyResponse:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout=None):
        return DummyResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = Dummy()
    result = backend.send(_message())
    assert result.ok is True
