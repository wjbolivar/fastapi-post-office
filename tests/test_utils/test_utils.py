from __future__ import annotations

from fastapi_post_office.utils import now_utc, redact


def test_redact_patterns():
    text = "token=abc password=secret"
    redacted = redact(text)
    assert "REDACTED" in redacted
    assert "secret" not in redacted


def test_now_utc_timezone():
    value = now_utc()
    assert value.tzinfo is not None
