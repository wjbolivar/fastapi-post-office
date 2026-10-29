"""Run with uvicorn examples.fastapi_app.app:app after explicit schema setup.

No SMTP/network I/O happens inside the route: a worker reads committed email rows.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import String, UniqueConstraint, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fastapi_post_office import AsyncEmailService, Settings
from fastapi_post_office.db import AsyncEmailRepository


class BusinessBase(DeclarativeBase):
    pass


class Signup(BusinessBase):
    __tablename__ = "example_signups"
    __table_args__ = (UniqueConstraint("request_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254))


class SignupInput(BaseModel):
    request_id: str
    email: str
    first_name: str


def create_app(
    database_url: str = "sqlite+aiosqlite:///./example.db", config: Settings | None = None
) -> FastAPI:
    config = config or Settings()
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await engine.dispose()

    app = FastAPI(lifespan=lifespan)
    app.state.engine = engine

    @app.post("/signup", status_code=201)
    async def signup(payload: SignupInput):
        # Authentication, rate limits and business idempotency belong to the host app.
        async with factory() as session, session.begin():
            existing = await session.scalar(
                select(Signup).where(Signup.request_id == payload.request_id)
            )
            if existing is not None:
                return {"signup_id": existing.id}
            row = Signup(request_id=payload.request_id, email=payload.email)
            session.add(row)
            service = AsyncEmailService(
                AsyncEmailRepository(session), config=config, auto_commit=False
            )
            message = await service.enqueue_template(
                template_name="welcome",
                to=[payload.email],
                context={"first_name": payload.first_name},
                idempotency_key=f"welcome:{payload.request_id}",
            )
            await session.flush()
            response = {"signup_id": row.id, "email_id": str(message.id)}
        return response

    return app


app = create_app()
