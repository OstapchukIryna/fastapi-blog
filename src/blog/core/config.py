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
        accesse_token_expire_minutes (int): how long an issued token
            stays valid.
        max_upload_size_bytes (int): ceiling for an uploaded profile
            picture, checked before the image is decoded.
        posts_per_page (int): default slice size for every paged list.
            A default, not a limit: the ceiling lives on the request
            model, where a caller can be refused.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    secret_key: SecretStr
    algorithm: str = "HS256"
    accesse_token_expire_minutes: int = 30

    max_upload_size_bytes: int = 5 * 1024 * 1024
    posts_per_page: int = 10


settings = Settings()
