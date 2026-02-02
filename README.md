# FastAPI Post Office 📬

![CI](https://github.com/wjbolivar/fastapi-post-office/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Coverage](https://img.shields.io/badge/coverage-88%25-brightgreen.svg)

---

## Overview

**FastAPI Post Office** is a production-grade library for managing **transactional email delivery**
in FastAPI and Python applications.

It treats email as **core infrastructure**.


---

## Why FastAPI Post Office?

Most email libraries focus only on *sending* messages.

FastAPI Post Office focuses on the **entire lifecycle**:

- What was sent?
- When?
- Using which template version?
- Did it fail? Was it retried?
- Can it be audited or reproduced later?

This makes it suitable for **real production systems**, regulated environments,
and long-running platforms where email delivery must be predictable and traceable.

---

## Architecture Overview

```
Application
   ↓
FastAPI Post Office
   ├── EmailService (public API)
   ├── Template Renderer
   ├── Repository (SQLAlchemy)
   ├── Email Backends
   ├── Celery Tasks (optional)
   └── CLI (sync-templates)
```

- Core logic is synchronous and deterministic
- Asynchronous behavior is delegated to Celery
- ORM: SQLAlchemy 2.x

Async stack:
- Optional async engine/session/repository/service are available
- Backends remain sync and are executed in a threadpool from async service

---

## Template System

Templates are stored as files and treated as the **source of truth**.

```
templates/
  welcome_user/
    manifest.json
    subject.j2
    html.j2
    text.j2
```

### `manifest.json`

```json
{
  "name": "welcome_user",
  "revision": 2,
  "description": "Welcome email after signup",
  "required_vars": ["first_name"],
  "tags": ["auth", "onboarding"]
}
```

**Rules**

- `revision` must increase monotonically
- Content changes without a revision bump fail fast
- Templates are validated before syncing

---

## Basic Usage

### Enqueue an email using a template

```python
await fapo.enqueue_template(
    template_name="welcome_user",
    to=["user@example.com"],
    context={"first_name": "William"},
    idempotency_key="welcome_user:user:123"
)
```

### Enqueue a raw email

```python
await fapo.enqueue(
    to=["user@example.com"],
    subject="Hello",
    html="<b>Hello</b>",
    text="Hello"
)
```

### Send immediately (without Celery)

```python
await fapo.send_now(message_id)
```

---

## Async Usage (optional)

```python
from fastapi_post_office.db import (
    AsyncEmailRepository,
    create_async_engine_from_url,
    create_async_session_factory,
)
from fastapi_post_office.service import AsyncEmailService

engine = create_async_engine_from_url("sqlite+aiosqlite:///./fapo_async.db")
session_factory = create_async_session_factory(engine)

async with session_factory() as session:
    repo = AsyncEmailRepository(session)
    service = AsyncEmailService(repo)
    await service.enqueue(
        to=["user@example.com"],
        subject="Hello",
        html="<b>Hello</b>",
        text="Hello",
        idempotency_key="raw:user:123",
    )
```

---

## Retry Policy

Default retry schedule:

| Attempt | Delay |
|--------|-------|
| 1 | Immediate |
| 2 | +60 seconds |
| 3 | +120 seconds |
| 4 | Mark as FAILED |

Retry behavior is configurable via environment variables.

---

## CLI — Sync Templates

Templates are synced into the database using a CLI command:

```bash
fapo sync-templates --path ./templates --upsert
```

Designed for CI/CD and production deployments.

---

## Development & Admin

An optional admin interface is available **for development only** and disabled by default. It is not required for production operation.

---

## Security Model

- Sandboxed template rendering
- No email bodies logged by default
- Template context is not persisted unless explicitly enabled
- Credentials loaded only from environment variables
- Fail-fast checks for unsafe configurations

---

## Installation

```bash
pip install fastapi-post-office
```

Development install:

```bash
pip install -e ".[dev,smtp,celery,admin]"
```

Async DB support (optional):

```bash
pip install "fastapi-post-office[db-sqlite-async]"
```

### Database driver note

FastAPI Post Office uses **SQLAlchemy sync**. Do **not** use async drivers like
`postgresql+asyncpg`. Use a sync driver such as:

- `postgresql+psycopg://...`
- `sqlite+pysqlite:///...`

Async stack requires an async driver, e.g.:

- `postgresql+asyncpg://...`
- `sqlite+aiosqlite:///...`

### Async production notes

- Prefer a managed pool (e.g. `asyncpg` with default SQLAlchemy pooling)
- Tune pool size and timeouts at the app level if you expect bursts
- Keep async DB usage in the async stack (avoid mixing sync sessions)

---

## License

MIT
