"""Handing the mail sender to a service that must not know about it.

services/passwords.py says what it needs — something it can call with an
address, a name and a token — and nothing about SMTP, templates, or when
delivery happens. This is where the "when" is decided, because it is a
property of the response rather than of the reset: the message goes out
after the body has, and the queue that arranges that belongs to a request.

This is the composition root for that dependency. It is the only place
where "a reset link is delivered" and "aiosmtplib talks to a server" are
named in the same file.
"""

from dataclasses import dataclass

from fastapi import BackgroundTasks

from blog.infrastructure import email


@dataclass(frozen=True, slots=True)
class BackgroundMail:
    """Delivery queued for after the response has been sent.

    Composition rather than inheritance, and the difference is not
    academic here. Subclassing BackgroundTasks would expose `add_task` to
    the service and let it queue anything at all — which is the whole
    interface this class exists to narrow. Holding one instead means the
    service can do exactly one thing with it.

    Satisfies `services.passwords.ResetMailer` by shape. It does not
    import that protocol and does not need to: presentation may import
    services, but keeping even this edge unwritten means the sender and
    the rule that uses it can be read, and changed, apart.

    Attributes:
        tasks (BackgroundTasks): this response's queue, filled by the
            route and drained by Starlette once the body has gone out.
    """

    tasks: BackgroundTasks

    def __call__(self, *, to_email: str, username: str, token: str) -> None:
        """Queue the reset email behind the current response.

        After the response rather than before it, for two reasons: an
        unreachable mail server then delays nobody, and the time taken to
        send does not differ measurably between an address that has an
        account and one that does not.

        Args:
            to_email (str): where to send it.
            username (str): how to address them.
            token (str): the one-time token, in the clear.
        """
        self.tasks.add_task(
            email.send_password_reset,
            to_email=to_email,
            username=username,
            token=token,
        )
