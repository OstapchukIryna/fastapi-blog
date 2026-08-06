"""Application settings and the paths that are not part of the package.

Settings are read once at import time and shared. Reading them lazily
would spread the failure: a missing SECRET_KEY should stop the process at
startup, not surface as a 500 on whichever request happens to need it
first.
"""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# * Repository root, derived from this file rather than from the working
# * directory: templates/, static/ and media/ live outside the package,
# * and Jinja and StaticFiles have to find them no matter which directory
# * the process was started from.
# * src/blog/core/config.py -> core -> blog -> src -> here.
BASE_DIR = Path(__file__).resolve().parents[3]

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
MEDIA_DIR = BASE_DIR / "media"

# * What the site calls itself. Down here rather than beside the Jinja
# * globals in presentation/web/templating.py, because two layers need it:
# * the pages put it in the navbar, and infrastructure/email.py signs
# * outgoing mail with it. Applying the usual test — would this make sense
# * if neither the web templating nor the mailer existed? — it would, so
# * it is shared vocabulary and belongs below both.
# *
# ! The email said "FastAPI Blog" for a while, which is the name of the
# ! framework rather than of anything a reader has visited. A brand kept
# ! in two files is a brand that ends up with two values.
SITE_HANDLE = "called_mad"
SITE_NAME = "Iryna Ostapchuk"


class Settings(BaseSettings):
    """Everything the application reads from the environment.

    Values come from real environment variables first and from `.env`
    second, which is what lets the test runs override the secret without
    touching the file.

    Attributes:
        secret_key (SecretStr): signs and verifies JWTs. Deliberately has
            no default — a shipped default secret is a secret everybody
            knows. SecretStr rather than str so it cannot be printed by
            accident in a traceback or a log line.
        algorithm (str): JWT signing algorithm.
        access_token_expire_minutes (int): how long an issued token
            stays valid.
        max_upload_size_bytes (int): ceiling for an uploaded profile
            picture, checked before the image is decoded.
        posts_per_page (int): default slice size for every paged list.
            A default, not a limit: the ceiling lives on the request
            model, where a caller can be refused.
        reset_token_expire_minutes (int): how long a password-reset link
            stays usable. Shorter than a session on purpose — the link
            travels through email, which is not a private channel.
        mail_server (str): SMTP host.
        mail_port (int): SMTP port.
        mail_username (str): SMTP user, empty when the server wants none.
        mail_password (SecretStr): SMTP password.
        mail_from (str): the From address on outgoing mail.
        mail_use_tls (bool): whether to STARTTLS after connecting.
        frontend_url (str): origin the reset link is built against. The
            application does not know its own public address, and
            guessing it from the request would let a forged Host header
            put an attacker's domain into an email we send.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Needs to be taken from the environment
    database_url: str

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    max_upload_size_bytes: int = 5 * 1024 * 1024
    posts_per_page: int = 10

    reset_token_expire_minutes: int = 30

    mail_server: str = "localhost"
    # * 587 is submission with STARTTLS. The previous value, 578, is not
    # * an SMTP port at all — mail would have gone nowhere, slowly.
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True

    # ! The name has to match the environment variable: pydantic-settings
    # ! maps FRONTEND_URL onto frontend_url. It was spelt `fromtend_url`,
    # ! so .env.example's FRONTEND_URL was never read and every reset
    # ! link in every email pointed at the default.
    frontend_url: str = "http://localhost:8000"


settings = Settings()
