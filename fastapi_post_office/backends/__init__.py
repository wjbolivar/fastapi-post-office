from __future__ import annotations

from fastapi_post_office.config import settings

from .base import EmailBackend
from .console import ConsoleBackend
from .smtp import SMTPBackend


def get_backend(name: str | None = None) -> EmailBackend:
    backend_name = (name or settings.email_backend).lower().strip()
    if backend_name == "console":
        return ConsoleBackend()
    if backend_name == "smtp":
        return SMTPBackend()
    raise ValueError(f"Unsupported backend: {backend_name}")
