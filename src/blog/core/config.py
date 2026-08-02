from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень репозитория: src/blog/core/config.py → core → blog → src → сюда.
# Считается от файла, а не от рабочего каталога, потому что templates/,
# static/ и media/ лежат вне пакета — их читают Jinja и StaticFiles, и
# приложение должно подниматься из любого места, а не только из корня.
BASE_DIR = Path(__file__).resolve().parents[3]

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
MEDIA_DIR = BASE_DIR / "media"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    secret_key: SecretStr
    algorithm: str = "HS256"
    accesse_token_expire_minutes: int = 30

    max_upload_size_bytes: int = 5 * 1024 * 1024


settings = Settings()  # Loaded from .env
