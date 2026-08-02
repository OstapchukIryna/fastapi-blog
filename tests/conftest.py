"""
Fixtures for the browser tests.

The application is started as a real process against a throwaway
database, because Playwright drives a real browser and a browser needs
an address. Nothing here touches blog.db.
"""

import os
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


@pytest.fixture(scope="session")
def live_server(tmp_path_factory) -> Iterator[str]:
    """Seed a temporary database, serve it, and hand back the address."""
    work = tmp_path_factory.mktemp("browser")
    env = {
        **os.environ,
        "SECRET_KEY": SECRET_KEY,
        "DATABASE_URL": f"sqlite+aiosqlite:///{work / 'test.db'}",
    }

    subprocess.run(
        [sys.executable, "seed.py"], cwd=ROOT, env=env, check=True, capture_output=True
    )

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
            if httpx.get(f"{base_url}/api/posts", timeout=1).status_code == 200:
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
            "/api/users",
            json={"username": handle, "email": email, "password": PASSWORD},
        )
        created.raise_for_status()

        issued = api.post(
            "/api/users/token", data={"username": email, "password": PASSWORD}
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
