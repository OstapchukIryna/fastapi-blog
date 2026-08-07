"""Application settings and the paths that are not part of the package.

Settings are read once at import time and shared. Reading them lazily
would spread the failure: a missing SECRET_KEY should stop the process at
startup, not surface as a 500 on whichever request happens to need it
first.
"""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Needs to be taken from the environment
    database_url: str

    # JWT token configs
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # S3 configuration
    s3_bucket_name: str
    s3_region: str = "eu-north-1"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_endpoint_url: str | None = None

    # Pictures settings
    max_upload_size_bytes: int = 5 * 1024 * 1024
    posts_per_page: int = 10

    # Settings for reset password via email
    reset_token_expire_minutes: int = 30

    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True

    frontend_url: str = "http://localhost:8000"

    # Logging
    environment: Literal["development", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


settings = Settings()
