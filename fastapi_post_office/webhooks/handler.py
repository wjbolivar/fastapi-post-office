from __future__ import annotations

from typing import Any

from fastapi_post_office.db.models import SuppressionReason


class WebhookError(ValueError):
    pass


def parse_suppression_events(
    provider: str, payload: Any
) -> list[tuple[str, SuppressionReason, dict]]:
    provider = provider.lower().strip()
    if provider == "sendgrid":
        return _parse_sendgrid(payload)
    if provider == "postmark":
        return _parse_postmark(payload)
    if provider == "ses":
        return _parse_ses(payload)
    if provider == "sendpulse":
        return _parse_sendpulse(payload)
    raise WebhookError(f"Unsupported provider: {provider}")


def _parse_sendgrid(payload: Any) -> list[tuple[str, SuppressionReason, dict]]:
    events = []
    if not isinstance(payload, list):
        raise WebhookError("SendGrid payload must be a list")
    for item in payload:
        email = str(item.get("email", "")).lower().strip()
        event = str(item.get("event", "")).lower().strip()
        if not email:
            continue
        if event in {"bounce", "dropped"}:
            events.append((email, SuppressionReason.BOUNCE, item))
        elif event in {"spamreport", "complaint"}:
            events.append((email, SuppressionReason.COMPLAINT, item))
    return events


def _parse_postmark(payload: Any) -> list[tuple[str, SuppressionReason, dict]]:
    if not isinstance(payload, dict):
        raise WebhookError("Postmark payload must be an object")
    record_type = str(payload.get("RecordType", "")).lower().strip()
    email = str(payload.get("Email", "")).lower().strip()
    if not email:
        return []
    if record_type == "bounce":
        return [(email, SuppressionReason.BOUNCE, payload)]
    if record_type == "spamcomplaint":
        return [(email, SuppressionReason.COMPLAINT, payload)]
    return []


def _parse_ses(payload: Any) -> list[tuple[str, SuppressionReason, dict]]:
    if not isinstance(payload, dict):
        raise WebhookError("SES payload must be an object")
    notification_type = str(payload.get("notificationType", "")).lower().strip()
    events: list[tuple[str, SuppressionReason, dict]] = []
    if notification_type == "bounce":
        for recipient in payload.get("bounce", {}).get("bouncedRecipients", []):
            email = str(recipient.get("emailAddress", "")).lower().strip()
            if email:
                events.append((email, SuppressionReason.BOUNCE, payload))
    elif notification_type == "complaint":
        for recipient in payload.get("complaint", {}).get("complainedRecipients", []):
            email = str(recipient.get("emailAddress", "")).lower().strip()
            if email:
                events.append((email, SuppressionReason.COMPLAINT, payload))
    return events


def _parse_sendpulse(payload: Any) -> list[tuple[str, SuppressionReason, dict]]:
    events: list[tuple[str, SuppressionReason, dict]] = []
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise WebhookError("SendPulse payload must be list or object")

    for item in payload:
        email = str(item.get("email", "")).lower().strip()
        event = str(item.get("event", "")).lower().strip()
        if not email:
            continue
        if event == "bounce":
            events.append((email, SuppressionReason.BOUNCE, item))
        elif event in {"complaint", "spam"}:
            events.append((email, SuppressionReason.COMPLAINT, item))
    return events
