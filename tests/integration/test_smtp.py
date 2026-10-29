import os
import socket
from email import policy
from email.parser import BytesParser

import pytest

from fastapi_post_office import EmailService, Settings
from fastapi_post_office.backends.smtp import SMTPBackend
from fastapi_post_office.db import EmailStatus
from fastapi_post_office.queue import QueueManager

pytestmark = pytest.mark.integration


def test_real_smtp_delivery_and_mime(repo):
    if os.environ.get("FAPO_TEST_NETWORK") != "1":
        pytest.skip("Set FAPO_TEST_NETWORK=1 to bind a local SMTP test server")
    from aiosmtpd.controller import Controller

    received = []

    class Handler:
        async def handle_DATA(self, server, session, envelope):
            received.append(envelope)
            return "250 accepted"

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    controller = Controller(
        Handler(), hostname="127.0.0.1", server_hostname="localhost", port=port, ready_timeout=10
    )
    controller.start()
    try:
        config = Settings(
            email_backend="smtp", smtp_host="127.0.0.1", smtp_port=port, smtp_starttls=False
        )
        service = EmailService(repo, config=config, backend=SMTPBackend(config=config))
        msg = service.enqueue(
            to=["to@example.com"],
            cc=["cc@example.com"],
            bcc=["hidden@example.com"],
            subject="Prueba ñ",
            html="<b>Hola</b>",
            text="Hola",
            idempotency_key="smtp-real",
        )
        assert service.send_now(msg.id).status == EmailStatus.SENT
        assert len(received) == 1
        envelope = received[0]
        assert set(envelope.rcpt_tos) == {"to@example.com", "cc@example.com", "hidden@example.com"}
        mime = BytesParser(policy=policy.default).parsebytes(envelope.original_content)
        assert mime["Subject"] == "Prueba ñ"
        assert mime["Bcc"] is None
        assert mime["Message-ID"] == msg.provider_message_id
        assert mime.get_body(preferencelist=("plain",)).get_content().strip() == "Hola"
        assert mime.get_body(preferencelist=("html",)).get_content().strip() == "<b>Hola</b>"
        assert QueueManager(repo.session).inspect(msg.id)["attempts"][0]["outcome"] == "SENT"
    finally:
        controller.stop()
