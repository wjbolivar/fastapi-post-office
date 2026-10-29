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


@pytest.mark.parametrize(
    "items",
    [
        "a@example.com",
        [None],
        ["bad"],
        ["a@example.com,b@example.com"],
        ["a@example.com\r\n"],
        ["a@example.com\x00"],
        ["Name <a@example.com>"],
    ],
)
def test_reject_ambiguous_or_invalid_recipients(items):
    with pytest.raises(ValidationError):
        validate_recipients("to", items)


@pytest.mark.parametrize("value", [None, "Hello\r\n", "Hello\x00", ""])
def test_reject_invalid_subject(value):
    with pytest.raises(ValidationError):
        validate_subject(value)
