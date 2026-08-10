import pytest
from pydantic import ValidationError

from blog.core.config import Settings

BASE_KWARGS = {
    "database_url": "postgresql+psycopg://user:pw@localhost/db",
    "secret_key": "x" * 32,
    "s3_bucket_name": "some-bucket",
}


def make_settings(**overrides) -> Settings:
    # _env_file=None: this developer's real .env is not a fixture, and
    # reading it here would make these tests pass or fail depending on
    # values that have nothing to do with what each test is checking.
    # pyrefly: ignore [bad-argument-type]  # overrides is deliberately
    # generic here; each test's literal values are what's actually checked.
    return Settings(_env_file=None, **{**BASE_KWARGS, **overrides})


# --- secret_key: minimum length ----------------------------------------------
def test_secret_key_min_length_accepted():
    make_settings(secret_key="x" * 32)


def test_secret_key_too_short_error():
    with pytest.raises(ValidationError):
        make_settings(secret_key="x" * 31)


# --- algorithm: closed set ----------------------------------------------------
def test_algorithm_unknown_value_error():
    with pytest.raises(ValidationError):
        make_settings(algorithm="none")


def test_algorithm_hs512_accepted():
    make_settings(algorithm="HS512")


# --- production refuses dev-only defaults -------------------------------------
def test_production_localhost_mail_server_error():
    with pytest.raises(ValidationError):
        make_settings(environment="production", frontend_url="https://x.com")


def test_production_localhost_frontend_url_error():
    with pytest.raises(ValidationError):
        make_settings(environment="production", mail_server="smtp.example.com")


def test_production_with_real_values_accepted():
    make_settings(
        environment="production",
        mail_server="smtp.example.com",
        frontend_url="https://example.com",
    )


def test_development_keeps_localhost_defaults_accepted():
    # the same values that fail in production are exactly the useful
    # defaults for a laptop with nothing configured
    make_settings(environment="development")
