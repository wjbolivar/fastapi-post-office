from __future__ import annotations

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration for FastAPI Post Office.

    Safe defaults:
    - Console backend by default (no real email sending).
    - No body logging by default.
    """

    model_config = SettingsConfigDict(
        env_prefix="FAPO_",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    env: str = Field(default="development", description="development|staging|production")

    # Database
    database_url: str = Field(default="sqlite+pysqlite:///./fapo.db")

    # Backend selection
    email_backend: str = Field(default="console", description="console|smtp|ses|sendgrid|postmark|mailgun")
    default_from: str = Field(default="no-reply@example.com")
    default_reply_to: Optional[str] = None

    # Template rules
    strict_template_vars: bool = True
    max_template_bytes: int = 256_000  # 256KB safety limit

    # Retry policy (seconds)
    max_attempts: int = 3
    retry_schedule_seconds: List[int] = Field(default_factory=lambda: [0, 60, 120])

    # Retention / logging
    retention_days: int = 30
    log_body: bool = False
    persist_context: bool = False  # off by default (security)

    # Admin (dev only)
    admin_mode: str = Field(default="disabled", description="disabled|local_only|dev_public|secured")
    allow_insecure_admin: bool = False

    # SMTP settings (only used by SMTP backend)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_starttls: bool = True
    smtp_timeout_seconds: int = 10

    # Celery settings
    celery_broker_url: Optional[str] = None
    celery_backend_url: Optional[str] = None

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in {"development", "staging", "production"}:
            raise ValueError("env must be one of: development, staging, production")
        return v

    @field_validator("email_backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        v = v.lower().strip()
        allowed = {"console", "smtp", "ses", "sendgrid", "postmark", "mailgun"}
        if v not in allowed:
            raise ValueError(f"email_backend must be one of: {sorted(allowed)}")
        return v

    @field_validator("retry_schedule_seconds")
    @classmethod
    def validate_retry_schedule(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("retry_schedule_seconds must not be empty")
        if any(x < 0 for x in v):
            raise ValueError("retry_schedule_seconds must contain non-negative integers")
        # Ensure first attempt is immediate unless user explicitly wants otherwise
        if v[0] != 0:
            raise ValueError("retry_schedule_seconds must start with 0 (immediate first attempt)")
        return v

    @field_validator("admin_mode")
    @classmethod
    def validate_admin_mode(cls, v: str) -> str:
        v = v.lower().strip()
        allowed = {"disabled", "local_only", "dev_public", "secured"}
        if v not in allowed:
            raise ValueError(f"admin_mode must be one of: {sorted(allowed)}")
        return v

    def validate_runtime_safety(self) -> None:
        """
        Fail-fast for dangerous configurations.
        Call this at app startup / worker startup.
        """
        if self.env == "production" and self.admin_mode == "dev_public":
            raise RuntimeError("FAPO_ADMIN_MODE=dev_public is not allowed in production")

        if self.admin_mode == "dev_public" and not self.allow_insecure_admin:
            raise RuntimeError(
                "FAPO_ADMIN_MODE=dev_public requires FAPO_ALLOW_INSECURE_ADMIN=true (explicit opt-in)"
            )

        if self.email_backend == "smtp":
            if not self.smtp_host:
                raise RuntimeError("SMTP backend selected but FAPO_SMTP_HOST is not set")
            # Username/password may be optional for some SMTP relays; keep flexible.


settings = Settings()
