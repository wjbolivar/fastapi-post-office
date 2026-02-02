from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .config import settings

if TYPE_CHECKING:
    from .providers import register_provider
    from .service import AsyncEmailService, EmailService
    from .webhooks import parse_suppression_events

__all__ = [
    "AsyncEmailService",
    "EmailService",
    "parse_suppression_events",
    "register_provider",
    "settings",
]


def __getattr__(name: str) -> Any:
    if name == "EmailService":
        from .service import EmailService

        return EmailService
    if name == "AsyncEmailService":
        from .service import AsyncEmailService

        return AsyncEmailService
    if name == "register_provider":
        from .providers import register_provider

        return register_provider
    if name == "parse_suppression_events":
        from .webhooks import parse_suppression_events

        return parse_suppression_events
    raise AttributeError(name)
