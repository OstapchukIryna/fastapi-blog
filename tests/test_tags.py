import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.infrastructure import models
from tests.conftest import auth_header, create_test_post, create_test_user, login_user


# --- GET /api/tags: tags.with_counts ----------------------------------------
@pytest.mark.anyio
async def test_get_tags_empty(client: AsyncClient):
    response = await client.get("/api/tags")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.anyio
async def test_get_tags_most_used_first(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    await create_test_post(client, headers, tags=["python"])
    await create_test_post(client, headers, tags=["python", "sql"])
    await create_test_post(client, headers, tags=["python", "sql", "rust"])

    response = await client.get("/api/tags")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["items"] == [
        {"name": "python", "count": 3},
        {"name": "sql", "count": 2},
        {"name": "rust", "count": 1},
    ]


@pytest.mark.anyio
async def test_get_tags_ties_broken_by_name(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    await create_test_post(client, headers, tags=["rust"])
    await create_test_post(client, headers, tags=["python"])

    response = await client.get("/api/tags")

    assert response.status_code == 200
    data = response.json()
    # same count (1) on both — alphabetical order breaks the tie
    assert data["items"] == [
        {"name": "python", "count": 1},
        {"name": "rust", "count": 1},
    ]


@pytest.mark.anyio
async def test_get_tags_orphaned_tag_is_invisible(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post = await create_test_post(client, headers, tags=["python"])

    # letting go of the last post that used it deletes the row outright
    response = await client.patch(f"/api/posts/{post['id']}", json={"tags": []}, headers=headers)
    assert response.status_code == 200
    assert response.json()["tags"] == []

    response = await client.get("/api/tags")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0

    # independent check: the row is actually gone, not just uncounted
    row = await db_session.scalar(select(models.Tag).where(models.Tag.name == "python"))
    assert row is None


@pytest.mark.anyio
async def test_shared_tag_survives_while_another_post_still_uses_it(
    client: AsyncClient, db_session: AsyncSession
):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post1 = await create_test_post(client, headers, tags=["python"])
    await create_test_post(client, headers, tags=["python"])

    response = await client.patch(f"/api/posts/{post1['id']}", json={"tags": []}, headers=headers)
    assert response.status_code == 200

    row = await db_session.scalar(select(models.Tag).where(models.Tag.name == "python"))
    assert row is not None


@pytest.mark.anyio
async def test_delete_post_removes_its_orphaned_tag(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post = await create_test_post(client, headers, tags=["python"])

    response = await client.delete(f"/api/posts/{post['id']}", headers=headers)
    assert response.status_code == 204

    row = await db_session.scalar(select(models.Tag).where(models.Tag.name == "python"))
    assert row is None


@pytest.mark.anyio
async def test_replace_post_removes_its_orphaned_tag(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post = await create_test_post(client, headers, tags=["python"])

    response = await client.put(
        f"/api/posts/{post['id']}",
        json={"title": "t", "summary": "s", "content": "c", "tags": ["rust"]},
        headers=headers,
    )
    assert response.status_code == 200

    row = await db_session.scalar(select(models.Tag).where(models.Tag.name == "python"))
    assert row is None


@pytest.mark.anyio
async def test_get_tags_respects_limit(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    for tag in ["python", "sql", "rust"]:
        await create_test_post(client, headers, tags=[tag])

    response = await client.get("/api/tags?limit=2")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2


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
