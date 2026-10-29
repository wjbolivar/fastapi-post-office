"""Reproducible DB/queue throughput harness; uses a no-network backend.

Requires an empty dedicated SQLite file or PostgreSQL database/schema. Never point
this script at a production database. Outputs measurements, not performance promises.
"""

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi_post_office import EmailService
from fastapi_post_office.backends.base import EmailBackend, SendResult
from fastapi_post_office.db import (
    Base,
    EmailRepository,
    create_engine_from_url,
    create_session_factory,
)
from fastapi_post_office.queue import QueueManager


class Sink(EmailBackend):
    name = "sink"

    def send(self, message):
        return SendResult(ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--messages", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.messages < 1 or args.workers < 1:
        parser.error("messages and workers must be positive")
    engine = create_engine_from_url(args.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    run_id = uuid4().hex
    try:
        start = time.perf_counter()
        ids = []
        with factory() as session:
            service = EmailService(EmailRepository(session), backend=Sink(), auto_commit=False)
            for i in range(args.messages):
                ids.append(
                    service.enqueue(
                        to=["benchmark@example.test"],
                        subject="Benchmark",
                        text="Test",
                        idempotency_key=f"{run_id}:{i}",
                    ).id
                )
            session.commit()
        enqueue_seconds = time.perf_counter() - start

        def send(message_id):
            start = time.perf_counter()
            with factory() as session:
                EmailService(EmailRepository(session), backend=Sink()).send_now(message_id)
            return (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            timings = sorted(pool.map(send, ids))
        delivery_seconds = time.perf_counter() - start
        with factory() as session:
            metrics = QueueManager(session).metrics()
        print(
            json.dumps(
                {
                    "messages": args.messages,
                    "workers": args.workers,
                    "enqueue_per_second": args.messages / enqueue_seconds,
                    "delivery_per_second": args.messages / delivery_seconds,
                    "p50_ms": statistics.median(timings),
                    "p95_ms": timings[int((len(timings) - 1) * 0.95)],
                    "queue": metrics,
                },
                indent=2,
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
