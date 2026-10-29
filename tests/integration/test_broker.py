import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_real_broker_and_worker(postgres):
    broker = os.environ.get("FAPO_TEST_BROKER_URL")
    if not broker:
        pytest.skip("Set FAPO_TEST_BROKER_URL for broker integration")
    _, url = postgres
    script = Path(__file__).resolve().parents[2] / "scripts" / "broker_smoke.py"
    env = dict(
        os.environ,
        FAPO_DATABASE_URL=url,
        FAPO_CELERY_BROKER_URL=broker,
        FAPO_EMAIL_BACKEND="console",
    )
    result = subprocess.run(
        [sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=50
    )
    assert result.returncode == 0, result.stdout + result.stderr
