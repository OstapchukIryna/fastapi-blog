import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_post, create_test_user, login_user


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


@pytest.mark.anyio
async def test_get_post_not_found(client: AsyncClient):
    response = await client.get("/api/posts/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"


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
    assert data["author"]["username"] == "testuser"


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


@pytest.mark.anyio
async def test_replace_post_drops_omitted_fields(client: AsyncClient):
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
    assert data["content"] == "replaced content"
    # PUT is a full replacement: a field left out takes the model default,
    # rather than staying what it was — that is what makes PUT not PATCH.
    assert data["tags"] == []


@pytest.mark.anyio
async def test_update_post_partial_leaves_the_rest_alone(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    post = await create_test_post(client, headers, tags=["python"])

    response = await client.patch(
        f"/api/posts/{post['id']}",
        json={"title": "patched title"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "patched title"
    assert data["content"] == "this is content"
    assert data["tags"] == ["python"]


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
