from unittest.mock import AsyncMock, patch

import pytest

from blog.infrastructure import email


# --- email.send: the low-level message builder ------------------------------
@pytest.mark.anyio
async def test_send_plain_text_only():
    with patch("blog.infrastructure.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await email.send(to_email="reader@example.com", subject="Hello", plain_text="Hi there")

    mock_send.assert_awaited_once()
    message = mock_send.call_args.args[0]
    assert message["To"] == "reader@example.com"
    assert message["Subject"] == "Hello"
    assert not message.is_multipart()
    assert message.get_content().strip() == "Hi there"


@pytest.mark.anyio
async def test_send_with_html_alternative():
    with patch("blog.infrastructure.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await email.send(
            to_email="reader@example.com",
            subject="Hello",
            plain_text="Hi there",
            html_content="<p>Hi there</p>",
        )

    message = mock_send.call_args.args[0]
    assert message.is_multipart()
    html_part = message.get_body(preferencelist=("html",))
    assert html_part is not None
    assert "<p>Hi there</p>" in html_part.get_content()


# --- email.send_password_reset: template + the real send path --------------
@pytest.mark.anyio
async def test_send_password_reset_renders_template():
    with patch("blog.infrastructure.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await email.send_password_reset(
            to_email="reader@example.com", username="reader", token="abc123"
        )

    message = mock_send.call_args.args[0]
    assert message["To"] == "reader@example.com"
    assert message["Subject"] == "Reset your password"

    plain_text = message.get_body(preferencelist=("plain",)).get_content()
    assert "reset-password?token=abc123" in plain_text
    assert "reader" in plain_text

    html_content = message.get_body(preferencelist=("html",)).get_content()
    assert "reset-password?token=abc123" in html_content


@pytest.mark.anyio
async def test_send_password_reset_swallows_delivery_failure(caplog):
    with patch(
        "blog.infrastructure.email.aiosmtplib.send",
        new_callable=AsyncMock,
        side_effect=OSError("connection refused"),
    ):
        # must not raise — this runs as a background task with nobody left
        # to tell if it fails
        await email.send_password_reset(
            to_email="reader@example.com", username="reader", token="abc123"
        )

    assert "could not be delivered" in caplog.text
