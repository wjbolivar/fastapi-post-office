"""Exercise a real Celery worker and broker against an isolated test database."""

import os
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from sqlalchemy import select

from fastapi_post_office import EmailService, settings
from fastapi_post_office.db import (
    EmailAttempt,
    EmailMessage,
    EmailRepository,
    create_engine_from_url,
    create_session_factory,
)
from fastapi_post_office.tasks.send import send_message


def main():
    queue = "fapo_test_" + uuid4().hex
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    worker = None
    with tempfile.TemporaryFile(mode="w+") as log:
        try:
            worker = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "celery",
                    "-A",
                    "fastapi_post_office.tasks.send:celery_app",
                    "worker",
                    "--pool=solo",
                    "--concurrency=1",
                    "--loglevel=WARNING",
                    "--without-gossip",
                    "--without-mingle",
                    "--queues",
                    queue,
                    "--hostname",
                    queue + "@%h",
                ],
                stdout=log,
                stderr=log,
                env=os.environ.copy(),
            )
            with factory() as session:
                msg_id = (
                    EmailService(EmailRepository(session))
                    .enqueue(
                        to=["a@example.com"],
                        subject="Broker integration",
                        text="body",
                        idempotency_key=queue,
                    )
                    .id
                )
            for _ in range(4):
                send_message.apply_async(args=[str(msg_id)], queue=queue)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if worker.poll() is not None:
                    raise RuntimeError("Worker exited unexpectedly")
                with factory() as session:
                    msg = session.get(EmailMessage, msg_id)
                    if msg.status.value == "SENT":
                        assert msg.attempt_count == 1
                        assert (
                            len(
                                session.scalars(
                                    select(EmailAttempt).where(EmailAttempt.message_id == msg_id)
                                ).all()
                            )
                            == 1
                        )
                        print("Real broker/worker delivery passed")
                        return
                time.sleep(0.2)
            raise RuntimeError("Worker did not deliver before deadline")
        except Exception:
            log.seek(0)
            print(log.read(), file=sys.stderr)
            raise
        finally:
            if worker is not None:
                worker.terminate()
                try:
                    worker.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=5)
            engine.dispose()


if __name__ == "__main__":
    main()
