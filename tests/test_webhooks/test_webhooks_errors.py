from __future__ import annotations

import pytest

from fastapi_post_office.webhooks import parse_suppression_events


def test_webhooks_unsupported_provider():
    with pytest.raises(ValueError):
        parse_suppression_events("unknown", {})


def test_webhooks_sendgrid_invalid_payload():
    with pytest.raises(ValueError):
        parse_suppression_events("sendgrid", {})


def test_webhooks_postmark_invalid_payload():
    with pytest.raises(ValueError):
        parse_suppression_events("postmark", [])


def test_webhooks_ses_invalid_payload():
    with pytest.raises(ValueError):
        parse_suppression_events("ses", [])


def test_webhooks_sendpulse_invalid_payload():
    with pytest.raises(ValueError):
        parse_suppression_events("sendpulse", "bad")
