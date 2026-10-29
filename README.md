# FastAPI Post Office 📬

![CI](https://github.com/wjbolivar/fastapi-post-office/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)

---

## Overview

**FastAPI Post Office** is an alpha library (0.2.0) for managing **transactional email delivery**
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

The library provides a foundation for transactional email. Production use requires
provider integration tests, deployment monitoring, and the operational safeguards below.

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
from fapo import EmailService

service = EmailService(repo)

service.enqueue_template(
    template_name="welcome_user",
    to=["user@example.com"],
    context={"first_name": "William"},
    idempotency_key="welcome_user:user:123"
)
```

Tip: the recommended import is now the short alias `fapo`.

### Enqueue a raw email

```python
service.enqueue(
    to=["user@example.com"],
    subject="Hello",
    html="<b>Hello</b>",
    text="Hello",
    idempotency_key="hello:user:123",
)
```

### Send immediately (without Celery)

```python
service.send_now(message_id)
```

---

## Async Usage (optional)

```python
from fapo.db import (
    AsyncEmailRepository,
    create_async_engine_from_url,
    create_async_session_factory,
)
from fapo.service import AsyncEmailService

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

## Integration with existing SQLAlchemy + Alembic

If your project already manages its own `Base`, engine, and Alembic migrations:

### 1) Avoid `create_all()` in production

Use Alembic for schema changes. Reserve `create_all()` for tests or local prototypes.

### 2) Reuse your app session/engine

Sync:

```python
from fapo.db.repository import EmailRepository
from fapo.service import EmailService

def send_email(session):
    repo = EmailRepository(session)
    service = EmailService(repo)
    service.enqueue(...)
```

Async:

```python
from fapo.db.async_repository import AsyncEmailRepository
from fapo.service import AsyncEmailService

async def send_email(session):
    repo = AsyncEmailRepository(session)
    service = AsyncEmailService(repo)
    await service.enqueue(...)
```

### 3) Alembic `target_metadata` (multiple bases)

In your Alembic `env.py`:

```python
from app.db.base import Base as AppBase
from fapo.db import Base as FapoBase

target_metadata = [AppBase.metadata, FapoBase.metadata]
```

### 3.1) Create and run migrations (required)

FastAPI Post Office does **not** run migrations automatically.  
Your app must generate and apply migrations that include FAPO tables.

```bash
# create migration with your app + FAPO metadata
alembic revision --autogenerate -m "add fapo tables"

# apply migrations
alembic upgrade head
```

### 3.2) Example `env.py` (sync)

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.db.base import Base as AppBase
from fapo.db import Base as FapoBase

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = [AppBase.metadata, FapoBase.metadata]

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 3.3) Example `env.py` (async)

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.db.base import Base as AppBase
from fapo.db import Base as FapoBase

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = [AppBase.metadata, FapoBase.metadata]

def do_run_migrations(connection: Connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported for async env.py")
else:
    asyncio.run(run_migrations_online())
```

### 4) Admin portal

Mount admin with **your** engine:

```python
from fapo.admin import mount_admin

mount_admin(app, engine)  # disabled by default; see security configuration below
```

---

## Retry Policy

Default retry schedule:

| Attempt | Delay |
|--------|-------|
| 1 | Immediate |
| 2 | +60 seconds |
| 3 | +120 seconds; mark FAILED if unsuccessful |

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

An optional admin interface is disabled by default. Public development modes must not be used in production; secured mode requires an application-provided authentication backend.

---

## Security Model

- Sandboxed template rendering
- No email bodies logged by default
- Template context is not persisted unless explicitly enabled
- Credentials may be supplied through environment variables or Settings; keep them out of source control
- Fail-fast checks for unsafe configurations

---

## Installation

```bash
pip install fastapi-post-office
```

Note: the package exposes a short alias `fapo` for imports.

Development install:

```bash
pip install -e ".[dev,smtp,celery,admin]"
```

Async DB support (optional):

```bash
pip install "fastapi-post-office[db-sqlite-async]"
```

### Database driver note

The synchronous service uses **SQLAlchemy sync**. For this service, do **not** use drivers like
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


## Running delivery workers

Enqueueing persists a message; it does not publish a Celery task. Run both a worker
and **one** Beat scheduler to dispatch queued messages and retries every 10 seconds:

```bash
export FAPO_DATABASE_URL='postgresql+psycopg://...'
export FAPO_CELERY_BROKER_URL='amqp://...'
export FAPO_EMAIL_BACKEND=smtp
export FAPO_SMTP_HOST=smtp.example.com
celery -A fastapi_post_office.tasks.send:celery_app worker
celery -A fastapi_post_office.tasks.send:celery_app beat
```

The dispatcher publishes at most `FAPO_QUEUE_BATCH_SIZE` due messages per tick (default 100).
`FAPO_DISPATCH_INTERVAL_SECONDS` controls the interval (default 10 seconds). Worker processes reuse
DB connection pools; the queue has a `(status, next_attempt_at)` index. Apply an
Alembic migration for this new index when upgrading an existing installation.
For small installations, call `send_now(message.id)` directly without Celery.
Use `AsyncEmailService` inside async FastAPI routes; synchronous service calls
perform blocking database and network I/O.

## Delivery guarantees and transaction ownership

- A conditional database update claims each due message before network I/O. Duplicate
  tasks skip SENT, FAILED, SENDING and retries that are not yet due.
- A claimed attempt and its STARTED history row are committed together before sending.
  Explicit temporary rejections enter the retry policy. Unexpected backend exceptions
  and ambiguous transport results require reconciliation; exception text is not persisted.
- A worker crash or cancellation after claiming leaves SENDING. Inspect provider
  logs before manually marking it SENT or rescheduling it; never blindly reset all
  SENDING messages. SMTP and the database cannot commit atomically, so exactly-once
  delivery is not guaranteed. Ambiguous transport timeouts remain SENDING with an UNKNOWN
  attempt outcome and are not retried automatically. Monitor old SENDING messages and exhausted retries.
- Partial SMTP acceptance is FAILED with a reconciliation notice, because retrying
  all recipients would duplicate messages already accepted. SENT means provider
  acceptance, not confirmed inbox delivery.
- Idempotency keys are stripped, limited to 255 characters and unique in the database.
  Reusing a key returns the original message, even if the new payload differs.
- `auto_commit=True` preserves the original API: enqueue commits the supplied session.
  Use `auto_commit=False` to join an application transaction; enqueue only flushes, and
  the application must commit or roll back. `send_now` requires a dedicated session
  and rejects pending ORM changes or `auto_commit=False`. Previously flushed business
  changes cannot be detected reliably: never use a business session for delivery.
  Async sessions must use `expire_on_commit=False` (as the supplied factory does).
- The provider saved with the message is used for delivery, even if the default changes.
  Suppressions are checked again immediately before sending.

## Security boundaries

- `secured` admin requires a SQLAdmin `authentication_backend`; authentication and
  authorization policy remain the host application's responsibility. `local_only`
  restricts socket peers to loopback and is rejected in production. Do not expose
  this mode through a local reverse proxy. `dev_public` requires explicit opt-in.
- HTML template variables are escaped; subject and text bodies are not HTML escaped.
  Use `safe` only for trusted HTML. Template authors and raw HTML must be trusted:
  Jinja sandboxing is not a CPU/memory isolation boundary. Do not pass privileged
  objects or callables as context. Render limits do not prevent all resource exhaustion.
- Addresses must be individual mailbox strings (no display names or comma-separated
  lists). Control characters are rejected before trimming. Console output omits
  bodies, subjects and recipient addresses unless body logging is explicitly enabled
  (addresses remain omitted).
- SMTP STARTTLS verifies certificates and hostnames; password authentication requires STARTTLS. HTTPS provider URLs must use
  HTTPS without embedded credentials; redirects are refused. Provider configuration
  must be trusted and network egress restricted by the host application.
- Webhook helpers **only parse payloads**. Verify the provider signature, timestamp
  and replay policy before parsing or adding suppressions. They are not authenticated
  FastAPI webhook endpoints.
- Bodies and addresses are stored in the database. Restrict access, use encryption
  and define retention. Scheduled cleanup covers SENT and CANCELLED messages. FAILED requires explicit
  opt-in; SENDING is always preserved. Cleanup also removes associated history, and
  deletes at most 1000 messages per call. Retention deletes idempotency keys, so their
  deduplication guarantee lasts only while the message row exists.
- Run `pip-audit` regularly in the deployed environment. Minimum dependency versions
  were raised after the audit; this is not a guarantee against future vulnerabilities.
  The optional admin requires Starlette >=1.3.1; check compatibility with your FastAPI
  version before installing that extra. Core email delivery does not require Starlette.

## Scope compared with django-post-office

The current implementation supports persisted messages, revision-checked templates,
sync/async SQLAlchemy services, SMTP/SES SMTP and HTTP providers, suppression checks,
idempotency and Celery dispatch. It does **not yet establish feature or performance
superiority** over django-post-office. Attachments, priorities, bulk enqueue APIs,
SMTP connection reuse across messages, template revision history and authenticated
webhook integrations remain future work. Attempt history and operator events are now persisted.
`mailgun` has no built-in backend; use a registered custom provider if needed.

Reference: [django-post-office features](https://github.com/ui/django-post_office).
Jinja dependency floor follows its [sandbox security fixes](https://jinja.palletsprojects.com/en/stable/changes/).

## Verification

```bash
pip install -e '.[dev,celery,admin]'
pytest
ruff check --no-fix fastapi_post_office tests fapo
black --check fastapi_post_office tests fapo
mypy fastapi_post_office fapo
bandit -r fastapi_post_office -ll
pip-audit
```

Regression tests exercise actual SQLite sessions (sync and async), application transaction
rollback, immutable backend payloads, overlapping workers, uniqueness conflicts,
retry delays/exhaustion, cancellation and reconciliation, suppression after enqueue,
MIME/Bcc serialization, verified TLS configuration, admin access, HTML escaping,
HTTP URL/redirect policy and provider response identifiers.

The opt-in integration suite was executed locally against PostgreSQL 16, Redis 7,
a real Celery worker and a local SMTP server. It covers concurrent enqueue/delivery,
additive schema migration and actual SMTP envelope/MIME transmission. MySQL remains
experimental (DDL compilation only); hosted provider accounts and production topology
must be validated in the pilot. Python 3.10–3.14 execution is configured in CI; local
execution used Python 3.14.2.

## Implementation plan toward 1.0

1. **Implemented:** stabilize public errors, configuration/backend injection and transactional enqueue.
2. **Implemented:** add persisted attempt history and safe, explicit queue operations (inspect, cancel,
   retry, reconcile, retention), with optimistic concurrency checks.
3. **Implemented:** capture provider identifiers and expose aggregate queue/attempt metrics without PII.
4. **Implemented and locally validated:** exercise real SMTP, PostgreSQL and broker/worker integration; add a reproducible
   load harness and CI services. Keep unvalidated providers explicitly experimental.
5. **Implemented:** ship a runnable FastAPI transactional-outbox example, upgrade migration and API contract.
6. **Build/installation validated:** wheel and sdist are checked in isolation.
   **Release gate still pending:** run an application pilot, execute the CI version matrix
   and validate the actual provider account before tagging 1.0.0. Current version is 0.2.0.


## Public API contract (0.2, candidate for 1.0)

```python
from fapo import EmailService, AsyncEmailService, Settings, PostOfficeError
from fapo.db import EmailRepository, AsyncEmailRepository
from fapo import QueueManager, AsyncQueueManager

config = Settings(default_from="notifications@example.com", email_backend="console")
service = EmailService(EmailRepository(session), config=config, auto_commit=False)
message = service.enqueue(
    to=["user@example.com"], subject="Hello", text="Hello",
    idempotency_key="welcome:user:123",
)
# The caller owns the transaction:
session.commit()  # or rollback(); the email follows the same outcome
```

For async, use `AsyncEmailService(AsyncEmailRepository(session), ...)` and await its
methods. Constructors snapshot configuration, so later changes to global settings
or another service do not change this instance. Backends may be injected with
`backend=...`; injected backends own their transport configuration. Workers need
the same provider configuration as the producer. This version does not support
persisting multiple credential profiles for the same provider in a shared queue;
use separate queues/databases or a custom routing backend for that case.

The stable service methods are `enqueue`, `enqueue_template` and `send_now`.
`enqueue` accepts text, HTML, or both. All enqueue calls require an idempotency key.
`send_now` respects due dates and terminal states. Enqueue returns an ORM `EmailMessage`;
do not expose it directly as an API response because it contains addresses and bodies.
Use the UUID or a deliberately limited response model.

Domain exceptions derive from `PostOfficeError`: `ValidationError`, `IdempotencyError`,
`MessageNotFoundError`, `TemplateNotFoundError`, `SuppressedRecipientError`,
`TransactionModeError`, and `InvalidTransitionError`. Rendering errors derive from
`ValidationError`. SQLAlchemy/driver failures keep their original types and require
rollback by the transaction owner. Services must not share a session concurrently.

Custom backends implement `send(EmailPayload) -> SendResult`. The payload is an
immutable, detached snapshot, including tuple recipients and the idempotency key;
async delivery runs the synchronous backend in a thread. Return `retryable=False`
for permanent rejection and `ambiguous=True` when acceptance is unknown. An unexpected
exception is treated as ambiguous. Keep credentials, payloads and provider error
bodies out of `error_message`; provide a short stable `error_code` instead.
Do not put credentials in template context or operator notes.

## Queue operations and recovery

```bash
fapo queue list --status FAILED
fapo queue list --status SENDING --older-than-seconds 300
fapo queue inspect MESSAGE_UUID
fapo queue metrics --stuck-after-seconds 300
fapo queue transition MESSAGE_UUID cancel --expected-attempt 0 --actor ops --note 'User requested cancellation'
fapo queue transition MESSAGE_UUID retry --expected-attempt 3 --actor ops --note 'Transient incident resolved' --acknowledge-duplicate-risk
fapo queue cleanup --retention-days 30              # preview only
fapo queue cleanup --retention-days 30 --execute    # delete up to 1000 terminal rows
```

For SENDING, first stop/confirm termination of the original worker and check provider
logs. Choose `reconcile-sent`, `reconcile-failed` or `reconcile-retry`, pass the observed
`--expected-attempt`, an actor/note, and `--acknowledge-duplicate-risk`. Optionally record
`--provider-message-id` when confirming acceptance. A database claim token prevents a
late worker from overwriting the reconciliation, but cannot stop a network send already
in flight. The explicit acknowledgement is an operational precondition, not proof that
the worker stopped. Reconciliation and retries leave operator events, and attempt numbers
never reset. A retry grants `--additional-attempts` more attempts (default 3).

`QueueManager(session)` exposes `list_messages`, `inspect`, `transition`, `cleanup`
and `metrics`; `AsyncQueueManager` provides the same async operations. Mutations own
and commit a **dedicated** operator session. Metrics contain state counts, due count,
oldest due age, stuck count, attempt count and average duration. Export them through
your application's authenticated monitoring endpoint or metrics collector. History is
retained with the message; these are persisted observations, not lifetime counters.

## Upgrade existing 0.1 installations

Back up the database and stop producers, workers and Beat. In a new Alembic revision
whose `down_revision` points at your current application head:

```python
from alembic import op
from fastapi_post_office.migrations import upgrade_0_2

def upgrade():
    upgrade_0_2(op.get_bind())
```

Run `alembic upgrade head`, then restart all processes on the same package version.
The additive migration handles SQLite/PostgreSQL, adds claim/completion timestamps,
the CANCELLED status, attempt/event tables and the due index. It preserves message
rows and backfills completion for previously sent messages. Old SENDING rows have no
attempt record/token; reconcile them explicitly before any resend. Existing FAILED
rows without a completion timestamp are preserved by retention. Do not fabricate old
attempt history. New installations should create the full metadata through their
initial Alembic migration. No destructive automatic downgrade is provided.

## Runnable FastAPI transactional example

```bash
pip install -e '.[dev,fastapi,celery,db-sqlite-async]'
python -m examples.fastapi_app.setup
export FAPO_DATABASE_URL='sqlite+pysqlite:///./example.db'
export FAPO_CELERY_BROKER_URL='redis://127.0.0.1:56379/0'
export FAPO_EMAIL_BACKEND=console
uvicorn examples.fastapi_app.app:app
# In separate terminals using the same environment:
celery -A fastapi_post_office.tasks.send:celery_app worker
celery -A fastapi_post_office.tasks.send:celery_app beat
```

POST `/signup` with `{"request_id":"signup-123","email":"user@example.com","first_name":"Ana"}`.
The app saves the signup and rendered email together; the worker sees it only after
commit. The demo uses explicit `create_all` setup for local use only. Production apps
must supply migrations, authentication, rate limits and concurrent business-request
idempotency; the example's basic request lookup is not a general concurrency solution.

## Reproduce integration, load and distribution checks

```bash
pip install -e '.[dev,celery,admin,integration]'
docker compose -p fapo-validation -f compose.integration.yml up -d --wait
export FAPO_TEST_POSTGRES_URL='postgresql+psycopg://fapo:fapo-test-only@127.0.0.1:55432/fapo_test'
export FAPO_TEST_BROKER_URL='redis://127.0.0.1:56379/0'
export FAPO_TEST_NETWORK=1
pytest
python scripts/benchmark_queue.py --database-url sqlite+pysqlite:///./benchmark.db --messages 1000 --workers 4
python -m build
python scripts/check_wheel.py dist/*.whl
docker compose -p fapo-validation -f compose.integration.yml down -v
```

The PostgreSQL fixture creates/removes only its own random test schema. Tests never
send to real mail accounts. Benchmark runs use a no-network sink, dedicated databases,
and retain their test messages. A local 1000-message run with four threads measured
about 236 completed messages/s on SQLite and 189/s on PostgreSQL in Docker (p95 53 ms
and 36 ms respectively). These measure DB/queue overhead, **not SMTP throughput**,
exclude broker dispatch, and are not service-level guarantees. Tune dispatch batch size
and interval to your measured provider rate limit; defaults dispatch at most 10 new
messages/s before worker capacity, retries and duplicate tasks are considered.

## Release and compatibility policy

0.2 remains alpha. Before 1.0, complete the pilot and all CI gates; after 1.0, public
service signatures, exceptions, payload fields and documented configuration follow
semantic versioning. Breaking changes require a major release and migration notes;
security fixes may tighten unsafe behavior. Database changes always require an explicit
migration. Supported candidates are SQLite for small/local workloads and PostgreSQL
for multiple workers. MySQL and hosted SendGrid/Postmark/SendPulse/SES integrations remain
experimental until validated with the actual service; payload/response tests are not
account-level delivery certification. Pin deployments to a reviewed lock/constraints
file and rerun `pip-audit` after updates. No package is automatically published by CI.

Provider response references: [Postmark acceptance and MessageID](https://www.postmarkapp.com/developer/get-started),
[SendGrid message identifiers](https://www.twilio.com/docs/sendgrid/glossary/message-id),
[SendPulse SMTP payload](https://sendpulse.com/latam/integrations/api/smtp).


Local validation snapshot (2026-10-28): **153 tests passed, 90.31% coverage** with
all five opt-in integration tests enabled. Ruff, Black, mypy, Bandit and `pip check`
passed. The installed-environment vulnerability audit reported no known advisories
across 100 packages. Python 3.10 dependency resolution also succeeded.
The wheel and sdist were built in isolation, and the wheel was installed and smoke-tested
in a clean temporary virtual environment outside the checkout.
