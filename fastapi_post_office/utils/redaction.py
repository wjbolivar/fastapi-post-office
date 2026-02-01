from __future__ import annotations

import re

DEFAULT_PATTERNS = [
    re.compile(r"(?i)password=[^&\s]+"),
    re.compile(r"(?i)token=[^&\s]+"),
]


def redact(text: str) -> str:
    if text is None:
        return ""
    result = str(text)
    for pattern in DEFAULT_PATTERNS:
        result = pattern.sub("REDACTED", result)
    return result
