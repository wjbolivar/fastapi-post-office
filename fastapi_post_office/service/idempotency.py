from __future__ import annotations

from fastapi_post_office.db.repository import EmailRepository


class IdempotencyError(ValueError):
    pass


def ensure_idempotency(repo: EmailRepository, key: str):
    if not key or not str(key).strip():
        raise IdempotencyError("idempotency_key is required")

    existing = repo.get_message_by_idempotency(str(key).strip())
    if existing is not None:
        return existing
    return None
