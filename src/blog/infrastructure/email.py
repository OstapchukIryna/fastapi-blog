"""Sending mail, and the templates the messages are built from.

Infrastructure rather than presentation: this is an SMTP client and a
Jinja environment of its own, pointed at templates/email/. It deliberately
does not reuse the web templating module — that lives one layer up, and
importing it from here would point an arrow the wrong way.

Every message goes out as both plain text and HTML. A reader whose client
refuses HTML still gets a working link, which for a password reset is the
difference between an inconvenience and a locked account.
"""

import logging
from email.message import EmailMessage

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from blog.core.config import TEMPLATES_DIR, settings

logger = logging.getLogger(__name__)

_environment = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR / "email"),
    # ! Escaping on. A username goes into the greeting, and a username is
    # ! whatever somebody typed at registration.
    autoescape=select_autoescape(["html"]),
)


async def send(
    to_email: str, subject: str, plain_text: str, html_content: str | None = None
) -> None:
    """Deliver one message.

    Args:
        to_email (str): the recipient.
        subject (str): the subject line.
        plain_text (str): the body every client can read.
        html_content (str | None): the richer alternative, when there is
            one. Added second because a client picks the last part it
            understands.

    Raises:
        aiosmtplib.SMTPException: the server refused or was unreachable.
            Raised rather than swallowed: this is the low-level send, and
            a caller that cannot cope with a failure should not be the
            one deciding to ignore it.
    """
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(plain_text)

    if html_content:
        message.add_alternative(html_content, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.mail_server,
        port=settings.mail_port,
        username=settings.mail_username or None,
        password=settings.mail_password.get_secret_value() or None,
        start_tls=settings.mail_use_tls,
    )


async def send_password_reset(to_email: str, username: str, token: str) -> None:
    """Email somebody the link that lets them choose a new password.

    Args:
        to_email (str): where to send it.
        username (str): how to address them.
        token (str): the one-time token, in the clear. This is the only
            place it exists outside the requester's inbox — the database
            holds only its hash.
    """
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    minutes = settings.reset_token_expire_minutes

    plain_text = (
        f"Hi {username},\n\n"
        "You asked to reset your password. Open the link below to choose "
        "a new one:\n\n"
        f"{reset_url}\n\n"
        f"The link stops working in {minutes} minutes.\n\n"
        "If you did not ask for this, you can ignore this message — your "
        "password has not changed.\n"
    )

    template = _environment.get_template("password_reset.html")
    html_content = template.render(
        reset_url=reset_url, username=username, minutes=minutes
    )

    # ! Failures are logged, not raised. This runs as a background task,
    # ! which Starlette awaits after the response body has gone out — an
    # ! exception here does not reach the caller, it tears down the
    # ! connection instead, and the next request on it fails with a
    # ! socket hang up that says nothing about mail. There is also nobody
    # ! left to tell: the answer was deliberately the same whether or not
    # ! an account exists, so it cannot now become "sending failed".
    try:
        await send(
            to_email=to_email,
            subject="Reset your password",
            plain_text=plain_text,
            html_content=html_content,
        )
    except Exception:
        logger.exception("password reset email could not be delivered")
