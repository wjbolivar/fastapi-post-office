from __future__ import annotations

import hashlib
from pathlib import Path


def compute_source_hash(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        if not path.exists():
            continue
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()
