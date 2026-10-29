from __future__ import annotations

from ipaddress import ip_address
from typing import ClassVar

from fastapi_post_office.config import settings


class _LocalOnlyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in {"http", "websocket"}:
            client = scope.get("client")
            try:
                allowed = bool(client) and ip_address(client[0]).is_loopback
            except ValueError:
                allowed = False
            if not allowed:
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await send({"type": "http.response.start", "status": 403, "headers": []})
                    await send({"type": "http.response.body", "body": b"Forbidden"})
                return
        await self.app(scope, receive, send)


def mount_admin(app, engine, *, authentication_backend=None) -> None:
    if settings.admin_mode == "disabled":
        return

    if settings.env == "production" and settings.admin_mode == "dev_public":
        raise RuntimeError("dev_public admin is not allowed in production")

    settings.validate_runtime_safety()
    if settings.admin_mode == "secured" and authentication_backend is None:
        raise RuntimeError("secured admin requires an authentication_backend")
    if settings.env == "production" and settings.admin_mode == "local_only":
        raise RuntimeError("Use secured admin in production; local_only is unsafe behind proxies")

    try:
        from sqladmin import Admin, ModelView
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "sqladmin is not installed. Install with fastapi-post-office[admin]."
        ) from exc

    from fastapi_post_office.db.models import EmailMessage, EmailTemplate

    class EmailTemplateAdmin(ModelView, model=EmailTemplate):
        column_list: ClassVar[list] = [
            EmailTemplate.name,
            EmailTemplate.revision,
            EmailTemplate.is_active,
        ]

    class EmailMessageAdmin(ModelView, model=EmailMessage):
        column_list: ClassVar[list] = [
            EmailMessage.id,
            EmailMessage.status,
            EmailMessage.template_name,
        ]

    kwargs = {}
    if authentication_backend is not None:
        kwargs["authentication_backend"] = authentication_backend
    admin = Admin(app, engine, **kwargs)
    if settings.admin_mode == "local_only":
        admin.admin.add_middleware(_LocalOnlyMiddleware)
    admin.add_view(EmailTemplateAdmin)
    admin.add_view(EmailMessageAdmin)
