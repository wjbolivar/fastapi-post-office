"""Install a built wheel in a fresh venv and smoke-test outside the repository."""

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    with tempfile.TemporaryDirectory(prefix="fapo-wheel-") as directory:
        root = Path(directory)
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        python = root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        subprocess.run(
            [str(python), "-m", "pip", "install", str(wheel)], cwd=root, env=env, check=True
        )
        code = """
from importlib.metadata import version
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fapo import EmailService, Settings
from fapo.db.models import EmailMessage
from fastapi_post_office.db import Base, EmailRepository
from fastapi_post_office.migrations import upgrade_0_2
from fastapi_post_office.queue import QueueManager
engine = create_engine("sqlite://")
Base.metadata.create_all(engine)
with Session(engine) as session:
    service = EmailService(EmailRepository(session), config=Settings(email_backend="console"))
    message = service.enqueue(to=["test@example.com"], subject="Wheel", text="Installed", idempotency_key="wheel")
    service.send_now(message.id)
    assert QueueManager(session).inspect(message.id)["attempts"][0]["outcome"] == "SENT"
print("Wheel installation verified:", version("fastapi-post-office"))
"""
        subprocess.run([str(python), "-c", code], cwd=root, env=env, check=True)
        cli = python.parent / ("fapo.exe" if os.name == "nt" else "fapo")
        subprocess.run([str(cli), "queue", "--help"], cwd=root, env=env, check=True)
        subprocess.run([str(python), "-m", "pip", "check"], cwd=root, env=env, check=True)


if __name__ == "__main__":
    main()
