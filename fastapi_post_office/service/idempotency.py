from __future__ import annotations

from typing import Protocol


class IdempotencyRepo(Protocol):
    def get_message_by_idempotency(self, key: str): ...


class AsyncIdempotencyRepo(Protocol):
    async def get_message_by_idempotency(self, key: str): ...


class IdempotencyError(ValueError):
    pass


def ensure_idempotency(repo: IdempotencyRepo, key: str):
    if not key or not str(key).strip():
        raise IdempotencyError("idempotency_key is required")

    existing = repo.get_message_by_idempotency(str(key).strip())
    if existing is not None:
        return existing
    return None


async def ensure_idempotency_async(repo: AsyncIdempotencyRepo, key: str):
    if not key or not str(key).strip():
        raise IdempotencyError("idempotency_key is required")

    existing = await repo.get_message_by_idempotency(str(key).strip())
    if existing is not None:
        return existing
    return None
