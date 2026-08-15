"""Application settings and the paths that are not part of the package.

Settings are read once at import time and shared. Reading them lazily
would spread the failure: a missing SECRET_KEY should stop the process at
startup, not surface as a 500 on whichever request happens to need it
first.
"""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# * src/blog/core/config.py -> core -> blog -> src -> here.
BASE_DIR = Path(__file__).resolve().parents[3]

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Site naming stuff
SITE_HANDLE = "called_mad"
SITE_NAME = "Iryna Ostapchuk"


class Settings(BaseSettings):
    """Everything the application reads from the environment.

    Values come from real environment variables first and from `.env`
    second, which is what lets the test runs override the secret without
    touching the file.
    """

    # * Resolved through BASE_DIR rather than left as the literal ".env":
    # * pydantic-settings reads that relative to the process's working
    # * directory, not this file's, so running from anywhere else would
    # * silently find no file and fail on a missing DATABASE_URL instead
    # * of on a missing .env.
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")

    # Needs to be taken from the environment
    database_url: str
    direct_database_url: str | None = None  # for migrations, if different from the pooled one
    plain_database_url: str | None = None

    @property
    def migration_database_url(self) -> str:
        """Direct connection string for migrations, if different is set."""
        return self.direct_database_url or self.database_url

    # owners' model
    owner_user_id: int | None = None

    # JWT token configs
    # * 32 bytes: short enough that PyJWT's own InsecureKeyLengthWarning
    # * would already say something, long enough that HMAC-SHA256 is not
    # * signing with less entropy than the hash it feeds.
    secret_key: SecretStr = Field(min_length=32)
    algorithm: Literal["HS256", "HS512"] = "HS256"
    access_token_expire_minutes: int = 30
    login_lockout_threshold: int = 5
    login_lockout_base_seconds: int = 1

    # S3 configuration
    s3_bucket_name: str
    s3_region: str = "eu-north-1"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_endpoint_url: str | None = None

    # Pictures settings
    max_upload_size_bytes: int = 5 * 1024 * 1024

    # Pagination
    posts_per_page: int = 10
    max_page_size: int = 100

    # Settings for reset password via email
    reset_token_expire_minutes: int = 30
    reset_token_cooldown_seconds: int = 60
    # * slowapi's own format ("N/period"), not just the count: the route
    # * decorator takes this string directly, so changing the limit means
    # * changing one value instead of keeping a string and a number in
    # * step by hand.
    forgot_password_rate_limit: str = "5/minute"

    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True

    frontend_url: str = "http://localhost:8000"

    trusted_hosts: list[str] = ["localhost", "127.0.0.1"]

    # Logging
    environment: Literal["development", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @model_validator(mode="after")
    def _reject_dev_defaults_in_production(self) -> Self:
        """Refuse to start in production with a value only a dev setup should carry.

        Both defaults are valid, working configuration for a laptop and
        silently wrong ones for a deployed site: mail through localhost
        works until the first real email, and a password-reset link
        pointing at localhost works until someone who isn't on that
        laptop clicks it. Neither fails loudly on its own — this is what
        turns "forgot to set MAIL_SERVER" into a startup error instead of
        a support ticket.
        """
        if self.environment == "production":
            if self.mail_server == "localhost":
                raise ValueError("mail_server must be set for production, not left as localhost")
            if "localhost" in self.frontend_url:
                raise ValueError("frontend_url must not point at localhost in production")
        return self

    def is_owner(self, user_id: int) -> bool:
        """Whether this id is the blog's owner.

        The one place the comparison is written: services/auth.py's
        Owner dependency enforces it, schemas/user.py's UserPrivate
        exposes it to the client. An unset owner_user_id means nobody
        holds the privilege, not that everybody does.
        """
        return self.owner_user_id is not None and self.owner_user_id == user_id


settings = Settings()
