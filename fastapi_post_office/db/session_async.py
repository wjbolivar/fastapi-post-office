from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_async_engine_from_url(database_url: str, echo: bool = False) -> AsyncEngine:
    if "+async" not in database_url and "+aiosqlite" not in database_url:
        raise RuntimeError(
            "Async engine requires an async driver (e.g. postgresql+asyncpg or sqlite+aiosqlite)."
        )
    return create_async_engine(database_url, echo=echo, future=True)


def create_async_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
