from __future__ import annotations

from collections.abc import Iterable
from email.headerregistry import Address

from fastapi_post_office.exceptions import ValidationError


def _check_header_injection(value: str, field: str) -> None:
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValidationError(f"Invalid header value in {field}")


def _mailbox(value: str, field: str) -> str:
    _check_header_injection(value, field)
    value = value.strip()
    try:
        address = Address(addr_spec=value)
        if not address.username or not address.domain or len(value) > 254:
            raise ValueError("Incomplete address")
    except (ValueError, IndexError) as exc:
        raise ValidationError(f"Invalid mailbox in {field}") from exc
    return value


def validate_recipients(field: str, items: Iterable[str]) -> list[str]:
    if items is None or isinstance(items, (str, bytes)):
        raise ValidationError(f"{field} must be an iterable of mailbox strings")
    cleaned = list(dict.fromkeys(_mailbox(value, field) for value in items))
    if not cleaned:
        raise ValidationError(f"{field} must not be empty")
    return cleaned


def validate_subject(subject: str) -> str:
    _check_header_injection(subject, "subject")
    subject = subject.strip()
    if not subject:
        raise ValidationError("subject must not be empty")
    return subject


def validate_from(from_email: str) -> str:
    return _mailbox(from_email, "from_email")
