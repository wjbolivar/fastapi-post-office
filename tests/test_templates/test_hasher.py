from __future__ import annotations

from fastapi_post_office.templates.hasher import compute_source_hash


def test_hasher_changes(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("one", encoding="utf-8")
    b.write_text("two", encoding="utf-8")
    h1 = compute_source_hash(a, b)
    b.write_text("three", encoding="utf-8")
    h2 = compute_source_hash(a, b)
    assert h1 != h2
