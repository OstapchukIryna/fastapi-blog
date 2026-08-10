from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


# --- GET /api/health ----------------------------------------------------------
@pytest.mark.anyio
async def test_health_check_success(client: AsyncClient):
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_health_check_database_unreachable_error(client: AsyncClient):
    # this route checks on a connection of its own, outside DbSession and
    # the pool it draws from - so the failure has to be injected at that
    # same point, not on the session the rest of the app's requests use
    with patch("blog.main.check_database_alive", new_callable=AsyncMock, return_value=False):
        response = await client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database connection failed"


@pytest.mark.anyio
async def test_health_check_not_in_openapi_schema(client: AsyncClient):
    response = await client.get("/openapi.json")

    assert "/api/health" not in response.json()["paths"]
