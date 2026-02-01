from __future__ import annotations

import pytest

from fastapi_post_office.config import Settings


def test_validate_runtime_safety_dev_public_requires_opt_in():
    settings = Settings(admin_mode="dev_public", allow_insecure_admin=False)
    with pytest.raises(RuntimeError):
        settings.validate_runtime_safety()


def test_validate_env_invalid():
    with pytest.raises(ValueError):
        Settings(env="invalid")


def test_retry_schedule_must_start_with_zero():
    with pytest.raises(ValueError):
        Settings(retry_schedule_seconds=[10, 20])


def test_backend_invalid():
    with pytest.raises(ValueError):
        Settings(email_backend="invalid")
