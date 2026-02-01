from __future__ import annotations

import pytest

from fastapi_post_office.service.validator import (
    ValidationError,
    validate_from,
    validate_recipients,
    validate_subject,
)


def test_validate_recipients_ok():
    assert validate_recipients("to", ["a@example.com"]) == ["a@example.com"]


def test_validate_recipients_empty():
    with pytest.raises(ValidationError):
        validate_recipients("to", [])


def test_validate_subject_injection():
    with pytest.raises(ValidationError):
        validate_subject("Hello\nBcc: x")


def test_validate_from_ok():
    assert validate_from("no-reply@example.com") == "no-reply@example.com"
