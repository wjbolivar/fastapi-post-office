from __future__ import annotations

from fastapi_post_office.config import settings

from .smtp import SMTPBackend


class SESBackend(SMTPBackend):
    name = "ses"

    def send(self, message):
        if not settings.smtp_host:
            raise RuntimeError("SES backend requires SMTP settings (FAPO_SMTP_HOST)")
        return super().send(message)
