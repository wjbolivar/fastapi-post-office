import smtplib
from email import policy
from email.parser import BytesParser
from urllib.error import HTTPError
from urllib.request import Request, build_opener

import pytest

from fastapi_post_office.backends.console import ConsoleBackend
from fastapi_post_office.backends.http_base import HttpApiBackend, _NoRedirect
from fastapi_post_office.backends.smtp import SMTPBackend
from fastapi_post_office.config import settings
from fastapi_post_office.db.models import EmailMessage


def message():
    return EmailMessage(
        from_email="sender@example.com",
        to_json=["to@example.com"],
        cc_json=["cc@example.com"],
        bcc_json=["hidden@example.com"],
        subject="private-subject",
        text_body="private-text",
        html_body="<b>private-html</b>",
    )


def test_console_does_not_disclose_contents_or_addresses(capsys):
    ConsoleBackend().send(message())
    output = capsys.readouterr().out
    assert "private" not in output
    assert "@example.com" not in output
    settings.log_body = True
    ConsoleBackend().send(message())
    assert "private-text" in capsys.readouterr().out


def test_smtp_wire_message_hides_bcc_and_preserves_envelope(monkeypatch):
    captured = {}

    class WireSMTP(smtplib.SMTP):
        def __init__(self, *args, **kwargs):
            pass

        def __exit__(self, *args):
            return False

        def ehlo_or_helo_if_needed(self):
            pass

        def sendmail(self, sender, recipients, msg, *args):
            captured.update(sender=sender, recipients=recipients, msg=msg)
            return {}

    settings.smtp_starttls = False
    settings.smtp_username = None
    monkeypatch.setattr(smtplib, "SMTP", WireSMTP)
    assert SMTPBackend().send(message()).ok
    wire = BytesParser(policy=policy.default).parsebytes(captured["msg"])
    assert wire["Bcc"] is None
    assert set(captured["recipients"]) == {"to@example.com", "cc@example.com", "hidden@example.com"}
    assert wire.get_body(preferencelist=("plain",)).get_content().strip() == "private-text"
    assert wire.get_body(preferencelist=("html",)) is not None


def test_smtp_partial_delivery_must_not_retry_whole_message(monkeypatch):
    from tests.test_backends.test_smtp_backend import DummySMTP

    monkeypatch.setattr(
        DummySMTP, "send_message", lambda self, msg: {"bad@example.com": (550, b"no")}
    )
    monkeypatch.setattr(smtplib, "SMTP", DummySMTP)
    result = SMTPBackend().send(message())
    assert not result.ok
    assert not result.retryable


@pytest.mark.parametrize(
    "url", ["http://example.com", "file:///etc/passwd", "https://user:secret@example.com"]
)
def test_http_rejects_unsafe_url_before_building_payload(url):
    backend = HttpApiBackend()
    backend.api_url = url
    result = backend.send(message())
    assert not result.ok
    assert not result.retryable


def test_redirect_handler_refuses_credential_forwarding():
    request = Request("https://example.com", headers={"Authorization": "Bearer secret"})
    with pytest.raises(HTTPError):
        build_opener(_NoRedirect()).error(
            "http", request, None, 302, "Redirect", {"location": "https://attacker.example"}
        )


def test_smtp_refuses_plaintext_password(monkeypatch):
    settings.smtp_starttls = False
    settings.smtp_username = "user"
    settings.smtp_password = "secret"
    result = SMTPBackend().send(message())
    assert not result.ok and not result.retryable
    assert "secret" not in result.error_message


@pytest.mark.parametrize("code,retryable", [(401, False), (429, True), (503, True)])
def test_http_status_controls_retries_without_leaking_body(monkeypatch, code, retryable):
    class Backend(HttpApiBackend):
        api_url = "https://example.com"

        def build_payload(self, msg):
            return {}

    def fail(*args, **kwargs):
        raise HTTPError("https://example.com", code, "private body and token", {}, None)

    monkeypatch.setattr("urllib.request.OpenerDirector.open", fail)
    result = Backend().send(message())
    assert not result.ok
    assert result.retryable is retryable
    assert result.error_message == f"HTTP {code}"


@pytest.mark.parametrize("code,retryable", [(450, True), (550, False)])
def test_smtp_explicit_rejection_classification(monkeypatch, code, retryable):
    from tests.test_backends.test_smtp_backend import DummySMTP

    def reject(self, msg):
        raise smtplib.SMTPDataError(code, b"private server diagnostic")

    monkeypatch.setattr(DummySMTP, "send_message", reject)
    monkeypatch.setattr(smtplib, "SMTP", DummySMTP)
    result = SMTPBackend().send(message())
    assert not result.ok
    assert result.retryable is retryable
    assert not result.ambiguous
    assert result.error_message == f"SMTP {code}"


def test_smtp_timeout_after_data_is_ambiguous(monkeypatch):
    from tests.test_backends.test_smtp_backend import DummySMTP

    def timeout(self, msg):
        raise TimeoutError("private server details")

    monkeypatch.setattr(DummySMTP, "send_message", timeout)
    monkeypatch.setattr(smtplib, "SMTP", DummySMTP)
    result = SMTPBackend().send(message())
    assert not result.ok and result.ambiguous and not result.retryable
    assert "private" not in result.error_message
