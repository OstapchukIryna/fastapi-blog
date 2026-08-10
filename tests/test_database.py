import asyncio
from collections.abc import AsyncGenerator

import pytest

from blog.infrastructure import database


class _SlowConnection:
    """A connection whose execute() outlives any reasonable timeout."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, *args, **kwargs):
        await asyncio.sleep(10)


class _FakeEngineThatConnectsButNeverAnswers:
    """Opens fine - the connect_args={"connect_timeout": ...} case can't
    catch this, because the TCP handshake already succeeded by the time
    the query itself hangs."""

    def connect(self):
        return _SlowConnection()


@pytest.fixture
async def health_check_engine() -> AsyncGenerator[None]:
    """Only what check_database_alive() itself needs: an engine to check.

    Not `client` - that also pulls in db_session, mocked_aws, moto and a
    savepoint transaction, none of which check_database_alive() touches.
    """
    database.setup_engine()
    yield
    await database.teardown_engine()


@pytest.mark.anyio
async def test_check_database_alive_true_on_success(health_check_engine):
    assert await database.check_database_alive() is True


@pytest.mark.anyio
async def test_check_database_alive_false_on_slow_query(monkeypatch, caplog):
    monkeypatch.setattr(database, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(database, "_health_check_engine", _FakeEngineThatConnectsButNeverAnswers())

    assert await database.check_database_alive() is False
    # Not just "it returned False" - any exception in the try block would
    # do that. This confirms a timeout specifically caused it, not a typo
    # in the fake elsewhere in this file raising something else entirely.
    assert "TimeoutError" in caplog.text


@pytest.mark.anyio
async def test_check_database_alive_raises_before_setup_engine(monkeypatch):
    monkeypatch.setattr(database, "_health_check_engine", None)

    with pytest.raises(RuntimeError, match="setup_engine"):
        await database.check_database_alive()
