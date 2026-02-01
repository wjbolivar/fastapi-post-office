from __future__ import annotations

from typing import Iterable


class ValidationError(ValueError):
    pass


def _check_header_injection(value: str, field: str) -> None:
    if "\n" in value or "\r" in value:
        raise ValidationError(f"Header injection detected in {field}")


def validate_recipients(field: str, items: Iterable[str]) -> list[str]:
    if items is None:
        raise ValidationError(f"{field} must not be None")
    cleaned = [str(x).strip() for x in items if str(x).strip()]
    if not cleaned:
        raise ValidationError(f"{field} must not be empty")
    for value in cleaned:
        _check_header_injection(value, field)
    return cleaned


def validate_subject(subject: str) -> str:
    subject = str(subject).strip()
    if not subject:
        raise ValidationError("subject must not be empty")
    _check_header_injection(subject, "subject")
    return subject


def validate_from(from_email: str) -> str:
    from_email = str(from_email).strip()
    if not from_email:
        raise ValidationError("from_email must not be empty")
    _check_header_injection(from_email, "from_email")
    return from_email
