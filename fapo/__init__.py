"""Short public alias; submodules share the canonical implementation."""

import importlib
import sys

from fastapi_post_office import *  # noqa: F403

for _name in (
    "config",
    "queue",
    "migrations",
    "exceptions",
    "db",
    "db.base",
    "db.models",
    "db.repository",
    "db.async_repository",
    "db.session",
    "db.session_async",
    "service",
    "service.email_service",
    "service.async_email_service",
    "backends",
    "backends.base",
    "providers",
    "admin",
    "webhooks",
):
    sys.modules[f"fapo.{_name}"] = importlib.import_module(f"fastapi_post_office.{_name}")
