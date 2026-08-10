import asyncio

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


@pytest.mark.anyio
async def test_check_database_alive_true_on_success(client):
    # `client` only to guarantee setup_engine() has already run for this test
    assert await database.check_database_alive() is True


@pytest.mark.anyio
async def test_check_database_alive_false_on_slow_query(client, monkeypatch):
    monkeypatch.setattr(database, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(database, "_health_check_engine", _FakeEngineThatConnectsButNeverAnswers())

    assert await database.check_database_alive() is False
