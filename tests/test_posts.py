import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.infrastructure import models
from blog.services import posts as posts_service
from tests.conftest import auth_header, create_test_post, create_test_user, login_user


# --- GET /api/posts: list_posts ---------------------------------------------
@pytest.mark.anyio
async def test_get_posts_empty(
    client: AsyncClient,
):  # client - is a name of a fixture that pytest will find
    response = await client.get("/api/posts")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["has_more"] is False


@pytest.fixture
async def five_posts(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    for i in range(5):
        await create_test_post(
            client, headers, title=f"Post {i}", summary=f"Summary {i}", content=f"Content {i}"
        )


@pytest.mark.anyio
async def test_get_posts_default_pagination(client: AsyncClient, five_posts):
    response = await client.get("/api/posts")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 5
    assert data["has_more"] is False


@pytest.mark.anyio
async def test_get_posts_limit(client: AsyncClient, five_posts):
    response = await client.get("/api/posts?limit=2")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["has_more"] is True


@pytest.mark.anyio
async def test_get_posts_skip_limit(client: AsyncClient, five_posts):
    response = await client.get("/api/posts?skip=2&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["skip"] == 2
    assert data["has_more"] is True


# --- GET /api/posts/{post_id}: get_post -------------------------------------
@pytest.mark.anyio
async def test_get_post_not_found(client: AsyncClient):
    response = await client.get("/api/posts/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"


@pytest.mark.anyio
async def test_get_post_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post = await create_test_post(client, headers)

    response = await client.get(f"/api/posts/{post['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == post["id"]
    assert data["title"] == "my first post"
    assert data["content"] == "this is content"


# --- POST /api/posts: create_post -------------------------------------------
@pytest.mark.anyio
async def test_create_post_success(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    response = await client.post(
        "/api/posts",
        json={
            "title": "my first post",
            "summary": "a short summary",
            "content": "this is content",
        },
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "my first post"
    assert data["content"] == "this is content"
    assert data["author"]["id"] == user["id"]
    assert "id" in data
    assert "date_posted" in data
    assert (
        data["author"]["username"] == "testuser"
    )  # since eager loading is used, the author is included in the response'nj


@pytest.mark.anyio
async def test_create_post_unauthorized(client: AsyncClient):
    response = await client.post(
        "api/posts",
        json={
            "title": "my first post",
            "summary": "a short summary",
            "content": "this is content",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_create_post_with_tags_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    response = await client.post(
        "/api/posts",
        json={
            "title": "my first post",
            "summary": "a short summary",
            "content": "this is content",
            "tags": ["Python", " SQL", "python", ""],
        },
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["tags"] == ["python", "sql"]


# --- PUT /api/posts/{post_id}: update_all_post_fields -----------------------
@pytest.mark.anyio
async def test_replace_post_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post = await create_test_post(client, headers, tags=["python"])

    response = await client.put(
        f"/api/posts/{post['id']}",
        json={
            "title": "replaced title",
            "summary": "replaced summary",
            "content": "replaced content",
            "tags": ["rust"],
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "replaced title"
    assert data["summary"] == "replaced summary"
    assert data["content"] == "replaced content"
    assert data["tags"] == ["rust"]


@pytest.mark.anyio
async def test_replace_post_drops_omitted_tags(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post = await create_test_post(client, headers, tags=["python"])

    response = await client.put(
        f"/api/posts/{post['id']}",
        json={
            "title": "replaced title",
            "summary": "replaced summary",
            "content": "replaced content",
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "replaced title"
    # PUT is a full replacement: an omitted field takes the schema's
    # default, it does not stay what it was — that is what tells PUT and
    # PATCH apart.
    assert data["tags"] == []


@pytest.mark.anyio
async def test_replace_post_validation_error(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post = await create_test_post(client, headers)

    response = await client.put(
        f"/api/posts/{post['id']}",
        json={"summary": "replaced summary", "content": "replaced content"},
        headers=headers,
    )

    assert response.status_code == 422
    missing_fields = {tuple(error["loc"]) for error in response.json()["detail"]}
    assert missing_fields == {("body", "title")}


@pytest.mark.anyio
async def test_replace_post_wrong_user_error(client: AsyncClient):
    await create_test_user(client, username="user1", email="user1@example.com")
    token1 = await login_user(client, email="user1@example.com")
    post = await create_test_post(client, auth_header(token1))

    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.put(
        f"/api/posts/{post['id']}",
        json={"title": "hijacked", "summary": "hijacked", "content": "hijacked"},
        headers=auth_header(token2),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to edit this post"


@pytest.mark.anyio
async def test_replace_post_unauthorized(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    post = await create_test_post(client, auth_header(token))

    response = await client.put(
        f"/api/posts/{post['id']}",
        json={"title": "hijacked", "summary": "hijacked", "content": "hijacked"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_replace_post_not_found(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.put(
        "/api/posts/999",
        json={"title": "t", "summary": "s", "content": "c"},
        headers=auth_header(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"


# --- PATCH /api/posts/{post_id}: update_post_fields -------------------------
@pytest.mark.anyio
async def test_update_post_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    response = await client.post(
        "/api/posts",
        json={
            "title": "my first post",
            "summary": "a short summary",
            "content": "original content",
            "tags": ["python"],
        },
        headers=headers,
    )

    post_id = response.json()["id"]

    response = await client.patch(
        f"/api/posts/{post_id}", json={"title": "updated title"}, headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "updated title"
    assert data["content"] == "original content"
    assert data["summary"] == "a short summary"
    assert data["tags"] == ["python"]


@pytest.mark.anyio
async def test_update_wrong_user(client: AsyncClient):
    await create_test_user(client, username="user1", email="user1@example.com")
    token1 = await login_user(client, email="user1@example.com")

    response = await client.post(
        "/api/posts",
        json={"title": "User1's post", "content": "'User1's content", "summary": "User1's summary"},
        headers=auth_header(token1),
    )
    post_id = response.json()["id"]

    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.patch(
        f"/api/posts/{post_id}", json={"title": "User2's title"}, headers=auth_header(token2)
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to edit this post"


# --- DELETE /api/posts/{post_id}: delete_post_api ---------------------------
@pytest.mark.anyio
async def test_delete_post_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post = await create_test_post(client, headers)

    response = await client.delete(f"/api/posts/{post['id']}", headers=headers)
    assert response.status_code == 204

    again = await client.get(f"/api/posts/{post['id']}")
    assert again.status_code == 404


# --- services.posts: find_related and set_pinned (no JSON route) -----------
# Used only by the web pages, not the JSON API — tested here directly
# against the service, without going through either front door.
async def _load_post_with_tags(db_session: AsyncSession, post_id: int) -> models.Post:
    result = await db_session.execute(posts_service.base_query().where(models.Post.id == post_id))
    post = result.scalars().first()
    assert post is not None
    return post


@pytest.mark.anyio
async def test_find_related_only_post_returns_empty(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(client)
    token = await login_user(client)
    created = await create_test_post(client, auth_header(token))
    post = await _load_post_with_tags(db_session, created["id"])

    related = await posts_service.find_related(db_session, post)

    assert related == []


@pytest.mark.anyio
async def test_find_related_prefers_shared_tags(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    main = await create_test_post(client, headers, title="Main", tags=["python", "sql"])
    await create_test_post(client, headers, title="One shared tag", tags=["python"])
    await create_test_post(client, headers, title="No shared tags", tags=["rust"])

    post = await _load_post_with_tags(db_session, main["id"])
    related = await posts_service.find_related(db_session, post)

    assert len(related) == 1
    assert related[0].post.title == "One shared tag"
    assert related[0].shared == ["python"]


@pytest.mark.anyio
async def test_find_related_ranks_by_shared_count(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    main = await create_test_post(client, headers, title="Main", tags=["python", "sql", "rust"])
    await create_test_post(client, headers, title="One shared", tags=["python"])
    await create_test_post(client, headers, title="Two shared", tags=["python", "sql"])

    post = await _load_post_with_tags(db_session, main["id"])
    related = await posts_service.find_related(db_session, post)

    assert [r.post.title for r in related] == ["Two shared", "One shared"]


@pytest.mark.anyio
async def test_find_related_falls_back_to_newest_without_tag_match(
    client: AsyncClient, db_session: AsyncSession
):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    main = await create_test_post(client, headers, title="Main", tags=["python"])
    await create_test_post(client, headers, title="Other 1")
    await create_test_post(client, headers, title="Other 2")

    post = await _load_post_with_tags(db_session, main["id"])
    related = await posts_service.find_related(db_session, post)

    assert len(related) == 2
    assert all(r.shared == [] for r in related)


@pytest.mark.anyio
async def test_find_related_falls_back_when_post_has_no_tags(
    client: AsyncClient, db_session: AsyncSession
):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    main = await create_test_post(client, headers, title="Main")
    await create_test_post(client, headers, title="Other", tags=["python"])

    post = await _load_post_with_tags(db_session, main["id"])
    related = await posts_service.find_related(db_session, post)

    assert len(related) == 1
    assert related[0].shared == []


@pytest.mark.anyio
async def test_find_related_respects_limit(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    main = await create_test_post(client, headers, title="Main", tags=["python"])
    for i in range(3):
        await create_test_post(client, headers, title=f"Match {i}", tags=["python"])

    post = await _load_post_with_tags(db_session, main["id"])
    related = await posts_service.find_related(db_session, post, limit=2)

    assert len(related) == 2


@pytest.mark.anyio
async def test_set_pinned_pins_a_post(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(client)
    token = await login_user(client)
    created = await create_test_post(client, auth_header(token))
    post = await db_session.get(models.Post, created["id"])
    assert post is not None

    await posts_service.set_pinned(db_session, post, pinned=True)

    assert post.is_pinned is True


@pytest.mark.anyio
async def test_set_pinned_unpins_a_post(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(client)
    token = await login_user(client)
    created = await create_test_post(client, auth_header(token))
    post = await db_session.get(models.Post, created["id"])
    assert post is not None
    await posts_service.set_pinned(db_session, post, pinned=True)

    await posts_service.set_pinned(db_session, post, pinned=False)

    assert post.is_pinned is False


@pytest.mark.anyio
async def test_set_pinned_unpins_the_previous_post(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post1 = await create_test_post(client, headers)
    post2 = await create_test_post(client, headers)

    row1 = await db_session.get(models.Post, post1["id"])
    assert row1 is not None
    await posts_service.set_pinned(db_session, row1, pinned=True)

    row2 = await db_session.get(models.Post, post2["id"])
    assert row2 is not None
    await posts_service.set_pinned(db_session, row2, pinned=True)

    # independent check via a fresh query: set_pinned's own bulk UPDATE
    # does not sync row1's in-memory state, so re-read rather than trust it
    pinned_count = await db_session.scalar(
        select(func.count()).where(models.Post.is_pinned.is_(True))
    )
    assert pinned_count == 1

    still_pinned_id = await db_session.scalar(
        select(models.Post.id).where(models.Post.is_pinned.is_(True))
    )
    assert still_pinned_id == post2["id"]
