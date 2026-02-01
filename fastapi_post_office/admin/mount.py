from __future__ import annotations

from typing import ClassVar

from fastapi_post_office.config import settings


def mount_admin(app, engine) -> None:
    if settings.admin_mode == "disabled":
        return

    if settings.env == "production" and settings.admin_mode == "dev_public":
        raise RuntimeError("dev_public admin is not allowed in production")

    try:
        from sqladmin import Admin, ModelView
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("sqladmin is not installed. Install with fastapi-post-office[admin].") from exc

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

    admin = Admin(app, engine)
    admin.add_view(EmailTemplateAdmin)
    admin.add_view(EmailMessageAdmin)
