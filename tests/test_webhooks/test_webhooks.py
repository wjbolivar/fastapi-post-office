from __future__ import annotations

from fastapi_post_office.db.models import SuppressionReason
from fastapi_post_office.webhooks import parse_suppression_events


def test_parse_sendgrid():
    payload = [
        {"email": "a@example.com", "event": "bounce"},
        {"email": "b@example.com", "event": "spamreport"},
    ]
    events = parse_suppression_events("sendgrid", payload)
    assert events[0][1] == SuppressionReason.BOUNCE
    assert events[1][1] == SuppressionReason.COMPLAINT


def test_parse_postmark():
    payload = {"RecordType": "Bounce", "Email": "a@example.com"}
    events = parse_suppression_events("postmark", payload)
    assert events[0][1] == SuppressionReason.BOUNCE


def test_parse_ses():
    payload = {
        "notificationType": "Complaint",
        "complaint": {"complainedRecipients": [{"emailAddress": "a@example.com"}]},
    }
    events = parse_suppression_events("ses", payload)
    assert events[0][1] == SuppressionReason.COMPLAINT


def test_parse_sendpulse():
    payload = {"data": [{"email": "a@example.com", "event": "bounce"}]}
    events = parse_suppression_events("sendpulse", payload)
    assert events[0][1] == SuppressionReason.BOUNCE
