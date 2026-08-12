import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_post, create_test_user, login_user

# * Each of these pages resolves the JSON route it hands to the "load
# * more" button by name, through Feed.after -> request.url_for. Nothing
# * type-checks that string against the API's actual route names - a
# * rename there raises NoMatchFound only when a page is opened. This is
# * the test that would have caught it: it does not know a name changed,
# * it only knows the page has to render.


@pytest.mark.anyio
async def test_home_page_renders(client: AsyncClient):
    response = await client.get("/")

    assert response.status_code == 200


@pytest.mark.anyio
async def test_tags_index_page_renders(client: AsyncClient):
    response = await client.get("/tags")

    assert response.status_code == 200


@pytest.mark.anyio
async def test_tag_page_renders(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    await create_test_post(client, auth_header(token), tags=["python"])

    response = await client.get("/tags/python")

    assert response.status_code == 200


@pytest.mark.anyio
async def test_user_posts_page_renders(client: AsyncClient):
    user = await create_test_user(client)

    response = await client.get(f"/users/{user['id']}/posts")

    assert response.status_code == 200
