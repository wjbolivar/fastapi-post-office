from __future__ import annotations

from fastapi_post_office.cli import main


def test_cli_sync_templates_calls(monkeypatch):
    called = {"ok": False}

    def fake_sync(path: str, upsert: bool):
        called["ok"] = True
        assert path == "./templates"
        assert upsert is True

    monkeypatch.setattr(main, "sync_templates_command", fake_sync)
    main.sync_templates(path="./templates", upsert=True)
    assert called["ok"] is True
