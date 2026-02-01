from __future__ import annotations

from fastapi_post_office.config import settings
from fastapi_post_office.providers.registry import registry

from .base import EmailBackend
from .console import ConsoleBackend
from .postmark import PostmarkBackend
from .sendgrid import SendGridBackend
from .sendpulse import SendPulseBackend
from .ses import SESBackend
from .smtp import SMTPBackend


def _register_defaults() -> None:
    if registry.names():
        return
    registry.register("console", ConsoleBackend, override=True)
    registry.register("smtp", SMTPBackend, override=True)
    registry.register("ses", SESBackend, override=True)
    registry.register("sendgrid", SendGridBackend, override=True)
    registry.register("postmark", PostmarkBackend, override=True)
    registry.register("sendpulse", SendPulseBackend, override=True)


def get_backend(name: str | None = None) -> EmailBackend:
    backend_name = (name or settings.email_backend).lower().strip()
    _register_defaults()
    return registry.create(backend_name)
