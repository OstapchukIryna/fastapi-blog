import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_post, create_test_user, login_user

# --- GET /api/tags: tags.with_counts (not covered yet) --------------------


# --- GET /api/tags/{tag}/posts: posts.with_tag -----------------------------
@pytest.mark.anyio
async def test_get_tag_posts_filters_by_tag(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    await create_test_post(client, headers, title="Python post", tags=["python"])
    await create_test_post(client, headers, title="SQL post", tags=["sql"])

    response = await client.get("/api/tags/python/posts")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Python post"


@pytest.mark.anyio
async def test_get_tag_posts_unknown_tag_is_404(client: AsyncClient):
    response = await client.get("/api/tags/nonexistent/posts")

    assert response.status_code == 404
    assert response.json()["detail"] == "Tag not found"


@pytest.mark.anyio
async def test_get_tag_posts_empty_page_past_the_end_is_not_404(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    await create_test_post(client, headers, tags=["python"])

    response = await client.get("/api/tags/python/posts?skip=10&limit=5")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"] == []
