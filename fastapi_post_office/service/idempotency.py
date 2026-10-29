from __future__ import annotations

from typing import Protocol

from fastapi_post_office.exceptions import IdempotencyError


class IdempotencyRepo(Protocol):
    def get_message_by_idempotency(self, key: str): ...


class AsyncIdempotencyRepo(Protocol):
    async def get_message_by_idempotency(self, key: str): ...


def normalize_idempotency_key(key: str) -> str:
    if not isinstance(key, str) or not key.strip():
        raise IdempotencyError("idempotency_key is required")
    key = key.strip()
    if len(key) > 255:
        raise IdempotencyError("idempotency_key must not exceed 255 characters")
    return key


def ensure_idempotency(repo: IdempotencyRepo, key: str):
    key = normalize_idempotency_key(key)

    existing = repo.get_message_by_idempotency(str(key).strip())
    if existing is not None:
        return existing
    return None


async def ensure_idempotency_async(repo: AsyncIdempotencyRepo, key: str):
    key = normalize_idempotency_key(key)

    existing = await repo.get_message_by_idempotency(str(key).strip())
    if existing is not None:
        return existing
    return None
