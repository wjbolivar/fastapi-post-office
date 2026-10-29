from __future__ import annotations

from .smtp import SMTPBackend


class SESBackend(SMTPBackend):
    name = "ses"

    def send(self, message):
        if not self.config.smtp_host:
            raise RuntimeError("SES backend requires SMTP settings (FAPO_SMTP_HOST)")
        return super().send(message)
