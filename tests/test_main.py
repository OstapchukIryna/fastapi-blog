from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# --- GET /api/health ----------------------------------------------------------
@pytest.mark.anyio
async def test_health_check_success(client: AsyncClient):
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_health_check_database_unreachable_error(
    client: AsyncClient, db_session: AsyncSession
):
    with patch.object(db_session, "execute", AsyncMock(side_effect=Exception("connection lost"))):
        response = await client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database connection failed"
