import base64
import io
import json
from typing import ClassVar

import pytest

from fastapi_post_office import Settings
from fastapi_post_office.backends import get_backend
from fastapi_post_office.backends.postmark import PostmarkBackend
from fastapi_post_office.backends.sendgrid import SendGridBackend
from fastapi_post_office.backends.sendpulse import SendPulseBackend
from tests.test_backends.test_provider_payloads import _message


def response(data):
    return io.BytesIO(json.dumps(data).encode())


def test_postmark_tracks_real_id_and_rejects_errors():
    backend = PostmarkBackend()
    assert (
        backend.parse_success(
            response({"ErrorCode": 0, "MessageID": "real-id"})
        ).provider_message_id
        == "real-id"
    )
    result = backend.parse_success(response({"ErrorCode": 300, "Message": "private"}))
    assert not result.ok and not result.retryable and "private" not in result.error_message


def test_sendgrid_tracks_response_header():
    class Response:
        headers: ClassVar[dict[str, str]] = {"X-Message-Id": "request-id"}

    assert SendGridBackend().parse_success(Response()).provider_message_id == "request-id"


def test_sendpulse_payload_and_response():
    backend = SendPulseBackend()
    payload = backend.build_payload(_message())["email"]
    assert base64.b64decode(payload["html"]).decode() == "<b>Hi</b>"
    assert payload["cc"] == [{"email": "cc@example.com"}]
    assert payload["bcc"] == [{"email": "bcc@example.com"}]
    assert (
        backend.parse_success(response({"result": True, "id": "real-id"})).provider_message_id
        == "real-id"
    )
    assert not backend.parse_success(response({"result": False})).ok


@pytest.mark.parametrize(
    "backend,data",
    [
        (PostmarkBackend, {}),
        (PostmarkBackend, {"ErrorCode": 0, "MessageID": None}),
        (SendPulseBackend, {}),
        (SendPulseBackend, {"result": True, "id": None}),
    ],
)
def test_invalid_provider_response_is_rejected(backend, data):
    with pytest.raises((KeyError, ValueError)):
        backend().parse_success(response(data))


def test_response_size_is_bounded():
    with pytest.raises(ValueError):
        PostmarkBackend.read_json(io.BytesIO(b"x" * 65537))
    with pytest.raises(ValueError):
        PostmarkBackend.read_json(response([]))


def test_two_clients_do_not_share_credentials_or_url():
    a = get_backend(
        "sendgrid",
        config=Settings(sendgrid_api_key="a", sendgrid_base_url="https://a.example/send"),
    )
    b = get_backend(
        "sendgrid",
        config=Settings(sendgrid_api_key="b", sendgrid_base_url="https://b.example/send"),
    )
    assert a.build_headers()["Authorization"] == "Bearer a"
    assert b.build_headers()["Authorization"] == "Bearer b"
    assert a.api_url != b.api_url
