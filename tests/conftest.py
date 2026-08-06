"""
Fixtures for the browser tests.

The application is started as a real process against a throwaway
database, because Playwright drives a real browser and a browser needs
an address.

The database is PostgreSQL, the same engine the application runs on.
It used to be SQLite, and that was a quiet lie: the tests passed against
an engine nobody deploys, so anything the two disagree about — timezone
handling on a timestamp, what a unique index does with case — was
untested by construction. The token expiry check is the example that
already exists: `PasswordResetToken.expired` compares an aware datetime,
which works on Postgres and raises TypeError on SQLite.

! The schema comes from `alembic upgrade head`, not from
! `Base.metadata.create_all`. That is the whole point of the change.
! create_all builds the schema a second way, so a migration that has
! drifted from the models still gives green tests and fails on deploy.
! Here the tests run the same migrations production runs, from an empty
! database, every session.
"""

import os
import re
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import jwt
import pytest

ROOT = Path(__file__).resolve().parent.parent

# Fixed, and only ever used by these tests. The expired-token test needs
# to sign one itself, which is impossible without knowing it.
SECRET_KEY = "browser-tests-only-secret-at-least-32-bytes-long"

PASSWORD = "correct-horse-battery"

# Run in a child process rather than here, so the test session never opens
# a connection of its own to the database it is about to drop the schema
# of — an open session would make DROP SCHEMA wait on its own lock.
RESET_SCHEMA = """
import os
import psycopg

url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
with psycopg.connect(url, autocommit=True) as connection:
    connection.execute("DROP SCHEMA public CASCADE")
    connection.execute("CREATE SCHEMA public")
"""


def throwaway_database_url() -> str:
    """Work out which database the tests may destroy.

    Not named `test_…`: pytest does not collect from conftest, so nothing
    would have broken, but the prefix reads as "this is a test case" to
    every human who meets it.

    Derived from the application's own DATABASE_URL by suffixing the
    database name, rather than configured separately: one connection
    string to keep right, and the test database always lives beside the
    development one on the same host and credentials. TEST_DATABASE_URL
    overrides it when the two cannot be neighbours — a managed instance,
    say.

    ! Read through `settings`, not `os.getenv`. The application takes
    ! DATABASE_URL from .env via pydantic-settings, and .env is not in the
    ! process environment — reading the environment directly found
    ! nothing locally while the application ran perfectly, which is a
    ! confusing way to discover that the tests and the code they test
    ! disagreed about where configuration lives.

    Returns:
        str: the connection string for the test database.

    Raises:
        RuntimeError: when the result would be the development database.
            Every session drops the schema, so this guard is the
            difference between a test run and losing your posts.
    """
    from blog.core.config import settings

    development = settings.database_url
    override = os.getenv("TEST_DATABASE_URL")
    url = override or re.sub(r"/([^/?]+)(\?|$)", r"/\1_test\2", development)

    if url == development:
        raise RuntimeError(
            f"The test database must not be the development one: {url}. "
            "Every session drops its schema."
        )
    if not url.startswith("postgresql"):
        raise RuntimeError(
            f"The tests need PostgreSQL, the engine the application runs on. Got: {url}"
        )
    return url


def free_port() -> int:
    """
    Ask the operating system for a port nobody is using.

    Not a fixed number: a stray server left over from another session
    answered on the port this project usually takes, and the tests would
    have quietly passed against it.
    """
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run(command: list[str], env: dict[str, str], what: str) -> None:
    """Run a setup step, and fail loudly with its output if it did not work.

    `check=True` alone raises a CalledProcessError that prints the exit
    code and nothing else, which for a failed migration is the least
    useful half of what happened.

    Args:
        command (list[str]): argv to run from the repository root.
        env (dict[str, str]): environment for the child process.
        what (str): what the step was doing, for the error message.

    Raises:
        RuntimeError: the step exited non-zero, with its output attached.
    """
    done = subprocess.run(
        command, cwd=ROOT, env=env, capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise RuntimeError(f"{what} failed:\n{done.stdout}\n{done.stderr}")


@pytest.fixture(scope="session")
def live_server() -> Iterator[str]:
    """Migrate a throwaway database, seed it, serve it, hand back the address."""
    env = {
        **os.environ,
        "SECRET_KEY": SECRET_KEY,
        "DATABASE_URL": throwaway_database_url(),
    }

    # * Dropped and recreated rather than emptied. `alembic downgrade base`
    # * would be the tidier-looking reset, but it only works when the
    # * database is already under Alembic's control — a database left over
    # * from the create_all days has tables and no alembic_version, and
    # * downgrade would no-op and then upgrade would fail on tables that
    # * already exist. Dropping the schema makes the starting state the
    # * same every time regardless of what was there before.
    #
    # ! Scoped to the test database by throwaway_database_url(), which refuses
    # ! to return the development one.
    run([sys.executable, "-c", RESET_SCHEMA], env, "resetting the test schema")
    run([sys.executable, "-m", "alembic", "upgrade", "head"], env, "alembic upgrade")
    run([sys.executable, "seed.py"], env, "seeding")

    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "blog.main:app", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if server.poll() is not None:
            output = server.stdout.read().decode() if server.stdout else ""
            raise RuntimeError(f"the application exited before it answered:\n{output}")
        try:
            if httpx.get(f"{base_url}/api/v1/posts", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        server.terminate()
        raise RuntimeError(f"the application never answered on {base_url}")

    yield base_url

    server.terminate()
    server.wait(timeout=10)


@pytest.fixture
def api(live_server: str):
    """A client for the setup a test needs before it opens a browser."""
    with httpx.Client(base_url=live_server, timeout=10) as client:
        yield client


@pytest.fixture
def make_account(api, request):
    """
    Register somebody and sign them in, returning their id and token.

    Named after the test that asked, so a failed run says who is who
    rather than leaving a row called pm_user_1785412345678.
    """

    def factory(label: str = "someone") -> dict:
        handle = (
            f"{request.node.name}_{label}"[-40:].replace("[", "_").replace("]", "_")
        )
        email = f"{handle}@example.com"

        created = api.post(
            "/api/v1/users",
            json={"username": handle, "email": email, "password": PASSWORD},
        )
        created.raise_for_status()

        issued = api.post(
            "/api/v1/users/token", data={"username": email, "password": PASSWORD}
        )
        issued.raise_for_status()

        return {
            "id": created.json()["id"],
            "username": handle,
            "email": email,
            "token": issued.json()["access_token"],
        }

    return factory


@pytest.fixture
def sign_in(page, live_server: str):
    """
    Put a token where the pages look for it, once.

    Loads the origin first so that localStorage exists, then writes the
    token. The obvious alternative — add_init_script — plants it again on
    every navigation, which quietly undoes any clearToken() the page
    performs and makes a test of expiry unable to fail.

    Whatever is loaded next reads the token in <head> the way a returning
    visitor's browser would.
    """

    def apply(token: str) -> None:
        page.goto(f"{live_server}/")
        page.evaluate(
            "token => localStorage.setItem('accessToken', token)",
            token,
        )

    return apply


def expired_token(user_id: int) -> str:
    """A token that is genuinely ours and genuinely stale."""
    return jwt.encode(
        {"sub": str(user_id), "exp": int(time.time()) - 60},
        SECRET_KEY,
        algorithm="HS256",
    )
