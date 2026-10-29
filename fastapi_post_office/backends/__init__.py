from __future__ import annotations

from fastapi_post_office.config import Settings, settings
from fastapi_post_office.providers.registry import registry

from .base import EmailBackend
from .console import ConsoleBackend
from .postmark import PostmarkBackend
from .sendgrid import SendGridBackend
from .sendpulse import SendPulseBackend
from .ses import SESBackend
from .smtp import SMTPBackend


def _register_defaults() -> None:
    defaults = {
        "console": ConsoleBackend,
        "smtp": SMTPBackend,
        "ses": SESBackend,
        "sendgrid": SendGridBackend,
        "postmark": PostmarkBackend,
        "sendpulse": SendPulseBackend,
    }
    for name, backend in defaults.items():
        if name not in registry.names():
            registry.register(name, backend)


def get_backend(name: str | None = None, *, config: Settings | None = None) -> EmailBackend:
    config = config or settings
    backend_name = (name or config.email_backend).lower().strip()
    _register_defaults()
    backend = registry.create(backend_name)
    backend.config = config.model_copy(deep=True)
    if isinstance(backend, (SendGridBackend, PostmarkBackend, SendPulseBackend)):
        backend.api_url = getattr(backend.config, f"{backend.name}_base_url")
    return backend
