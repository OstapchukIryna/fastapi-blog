from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import ANY, AsyncMock, patch

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from blog.core.config import settings
from blog.infrastructure import models
from blog.schemas import UserCreate, UserUpdate
from blog.services import users
from tests.conftest import (
    PASSWORD,
    S3_BUCKET_NAME,
    auth_header,
    create_test_post,
    create_test_user,
    login_user,
)

# * --- POST /api/users: registration ------------------------------------------


@pytest.mark.anyio
async def test_create_user_success(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={"username": "newuser", "email": "newemail@example.com", "password": "newpassword123"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newemail@example.com"
    assert "id" in data
    assert "image_path" in data
    assert data["image_path"] == "/static/profile_pics/default.jpg"
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.anyio
async def test_create_user_email_lowercase(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={
            "username": "MixedCaseUser",
            "email": "Mixed@Example.COM",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "mixed@example.com"
    assert data["username"] == "MixedCaseUser"


@pytest.mark.anyio
async def test_create_user_validation_error(client: AsyncClient):
    response = await client.post("/api/users", json={"username": "testuser"})

    assert response.status_code == 422
    # {"detail": [
    #   {"type": "missing", "loc": ["body", "email"], "msg": "Field required", ...},
    #   {"type": "missing", "loc": ["body", "password"], "msg": "Field required", ...}]}

    missing_fields = {tuple(error["loc"]) for error in response.json()["detail"]}
    assert missing_fields == {("body", "email"), ("body", "password")}


@pytest.mark.anyio
async def test_create_user_duplicate_email_error(client: AsyncClient):
    await create_test_user(client)
    response = await client.post(
        "/api/users",
        json={"username": "different_user", "email": "test@example.com", "password": "password123"},
    )
    # data is perfectly valid, so it is not 422
    assert response.status_code == 400
    assert response.json()["detail"] == "Username or email already registered"


@pytest.mark.anyio
async def test_create_user_duplicate_username_error(client: AsyncClient):
    await create_test_user(client)
    response = await client.post(
        "/api/users",
        json={"username": "testuser", "email": "different@example.com", "password": "password123"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Username or email already registered"


@pytest.mark.anyio
async def test_create_user_duplicate_email_case_insensitive_error(client: AsyncClient):
    await create_test_user(client, username="user1", email="Case@Example.com")
    response = await client.post(
        "/api/users",
        json={"username": "user2", "email": "case@example.com", "password": "password123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username or email already registered"


@pytest.mark.anyio
async def test_create_user_duplicate_username_case_insensitive_error(client: AsyncClient):
    await create_test_user(client, username="CaseUser", email="user1@example.com")
    response = await client.post(
        "/api/users",
        json={"username": "caseuser", "email": "user2@example.com", "password": "password123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username or email already registered"


@pytest.mark.anyio
async def test_create_user_password_at_min_length_accepted(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={"username": "minpassuser", "email": "minpass@example.com", "password": "x" * 8},
    )

    assert response.status_code == 201


@pytest.mark.anyio
async def test_create_user_password_below_min_length_error(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={"username": "shortpassuser", "email": "shortpass@example.com", "password": "x" * 7},
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "password"]
    assert error["type"] == "string_too_short"


@pytest.mark.anyio
async def test_create_user_password_at_max_length_accepted(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={"username": "maxpassuser", "email": "maxpass@example.com", "password": "x" * 128},
    )

    assert response.status_code == 201


@pytest.mark.anyio
async def test_create_user_password_over_max_length_error(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={"username": "longpassuser", "email": "longpass@example.com", "password": "x" * 129},
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "password"]
    assert error["type"] == "string_too_long"


# * --- POST /api/users/token: login -------------------------------------------


@pytest.mark.anyio
async def test_login_success(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": PASSWORD},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.anyio
async def test_login_wrong_password_error(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect password or email"


@pytest.mark.anyio
async def test_login_unknown_email_error(client: AsyncClient):
    response = await client.post(
        "/api/users/token",
        data={"username": "nobody@example.com", "password": PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect password or email"


@pytest.mark.anyio
async def test_login_email_case_insensitive(client: AsyncClient):
    await create_test_user(client, email="Mixed@Example.com")

    response = await client.post(
        "/api/users/token",
        data={"username": "mixed@example.com", "password": PASSWORD},
    )

    assert response.status_code == 200


@pytest.mark.anyio
async def test_login_validation_error(client: AsyncClient):
    response = await client.post("/api/users/token", data={})

    assert response.status_code == 422
    missing_fields = {tuple(error["loc"]) for error in response.json()["detail"]}
    assert missing_fields == {("body", "username"), ("body", "password")}


# * --- GET /api/users/me: current user -----------------------------------------


@pytest.mark.anyio
async def test_current_user_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.get("/api/users/me", headers=auth_header(token))

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    # UserPrivate and account includes email
    assert data["email"] == "test@example.com"


@pytest.mark.anyio
async def test_current_user_no_token_error(client: AsyncClient):
    response = await client.get("/api/users/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_current_user_wrong_scheme_error(client: AsyncClient):
    response = await client.get("/api/users/me", headers={"Authorization": "Basic abc123"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_current_user_garbage_token_error(client: AsyncClient):
    response = await client.get(
        "/api/users/me", headers={"Authorization": "Bearer not-a-jwt-at-all"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.anyio
async def test_current_user_token_without_sub_error(client: AsyncClient):
    secret = settings.secret_key.get_secret_value()
    token = jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(minutes=5)}, secret, algorithm=settings.algorithm
    )

    response = await client.get("/api/users/me", headers=auth_header(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.anyio
async def test_current_user_token_without_exp_error(client: AsyncClient):
    secret = settings.secret_key.get_secret_value()
    token = jwt.encode({"sub": "1"}, secret, algorithm=settings.algorithm)

    response = await client.get("/api/users/me", headers=auth_header(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.anyio
async def test_current_user_expired_token_error(client: AsyncClient):
    secret = settings.secret_key.get_secret_value()
    token = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=5)},
        secret,
        algorithm=settings.algorithm,
    )

    response = await client.get("/api/users/me", headers=auth_header(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.anyio
async def test_current_user_forged_signature_error(client: AsyncClient):
    token = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "not-the-real-secret-but-still-32-bytes-long",
        algorithm=settings.algorithm,
    )

    response = await client.get("/api/users/me", headers=auth_header(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.anyio
async def test_current_user_deleted_account_error(client: AsyncClient):
    secret = settings.secret_key.get_secret_value()
    # a valid token with not valid user
    token = jwt.encode(
        {"sub": "99999", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        secret,
        algorithm=settings.algorithm,
    )

    response = await client.get("/api/users/me", headers=auth_header(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "User not found"


# * --- POST /api/users/forgot-password ----------------------------------------


@pytest.mark.anyio
async def test_forgot_password_send_email(client: AsyncClient):
    await create_test_user(client)

    with (
        patch(
            "blog.infrastructure.email.send_password_reset",  # ! gotcha that presentation/api/mail.py doesnt have a live link to that, it creates a reference,
            # ! when u are mocking somethig, u patch where the main is looked up, not where the function is defined
            new_callable=AsyncMock,  # not a monkeypatch, because a unittest returns an object that we can verify that the backgroundtask is actually awaited and returns arguments
        ) as mock_send
    ):
        response = await client.post(
            "/api/users/forgot-password",
            json={"email": "test@example.com"},
        )

        mock_send.assert_awaited_once_with(
            to_email="test@example.com", username="testuser", token=ANY
        )

    assert response.status_code == 202


@pytest.mark.anyio
async def test_forgot_password_unknown_email_no_email_sent(client: AsyncClient):
    with patch(
        "blog.infrastructure.email.send_password_reset",
        new_callable=AsyncMock,
    ) as mock_send:
        response = await client.post(
            "/api/users/forgot-password",
            json={"email": "nobody@example.com"},
        )

        mock_send.assert_not_awaited()

    # same 202 as a known address
    assert response.status_code == 202


# * --- POST /api/users/reset-password -----------------------------------------
@pytest.fixture
async def reset_token(client: AsyncClient) -> str:
    await create_test_user(client)

    with patch(
        "blog.infrastructure.email.send_password_reset",
        new_callable=AsyncMock,
    ) as mock_send:
        await client.post("/api/users/forgot-password", json={"email": "test@example.com"})

    return mock_send.call_args.kwargs["token"]


@pytest.mark.anyio
async def test_reset_password_success(client: AsyncClient, reset_token: str):
    response = await client.post(
        "/api/users/reset-password",
        json={"token": reset_token, "new_password": "newpassword123"},
    )

    assert response.status_code == 200

    # independent check: the new password actually works for signing in
    login_response = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "newpassword123"},
    )
    assert login_response.status_code == 200


@pytest.mark.anyio
async def test_reset_password_unknown_token_error(client: AsyncClient):
    response = await client.post(
        "/api/users/reset-password",
        json={"token": "not-a-real-token", "new_password": "newpassword123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "This reset link is invalid or has expired."


@pytest.mark.anyio
async def test_reset_password_reused_token_error(client: AsyncClient, reset_token: str):
    first = await client.post(
        "/api/users/reset-password",
        json={"token": reset_token, "new_password": "newpassword123"},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/users/reset-password",
        json={"token": reset_token, "new_password": "anotherpassword123"},
    )

    assert second.status_code == 400
    assert second.json()["detail"] == "This reset link is invalid or has expired."


@pytest.mark.anyio
async def test_reset_password_expired_token_error(
    client: AsyncClient, db_session: AsyncSession, reset_token: str
):
    result = await db_session.execute(select(models.PasswordResetToken))
    token_row = result.scalars().one()
    token_row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    response = await client.post(
        "/api/users/reset-password",
        json={"token": reset_token, "new_password": "newpassword123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "This reset link is invalid or has expired."

    # independent check: an expired token is deleted on use
    result = await db_session.execute(select(models.PasswordResetToken))
    assert result.scalars().first() is None


@pytest.mark.anyio
async def test_reset_password_validation_error(client: AsyncClient):
    response = await client.post("/api/users/reset-password", json={})

    assert response.status_code == 422
    missing_fields = {tuple(error["loc"]) for error in response.json()["detail"]}
    assert missing_fields == {("body", "token"), ("body", "new_password")}


@pytest.mark.anyio
async def test_reset_password_new_password_below_min_length_error(
    client: AsyncClient, reset_token: str
):
    response = await client.post(
        "/api/users/reset-password",
        json={"token": reset_token, "new_password": "x" * 7},
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "new_password"]
    assert error["type"] == "string_too_short"


@pytest.mark.anyio
async def test_reset_password_new_password_over_max_length_error(
    client: AsyncClient, reset_token: str
):
    response = await client.post(
        "/api/users/reset-password",
        json={"token": reset_token, "new_password": "x" * 129},
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "new_password"]
    assert error["type"] == "string_too_long"


# * --- PATCH /api/users/me/password: change password --------------------------


@pytest.mark.anyio
async def test_change_password_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": PASSWORD, "new_password": "newpassword123"},
        headers=auth_header(token),
    )

    assert response.status_code == 200

    # independent check: old password stops working
    old_login = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "newpassword123"},
    )
    assert new_login.status_code == 200


@pytest.mark.anyio
async def test_change_password_wrong_current_password_error(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": "not-the-real-password", "new_password": "newpassword123"},
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect."


@pytest.mark.anyio
async def test_change_password_unauthorized(client: AsyncClient):
    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": PASSWORD, "new_password": "newpassword123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_change_password_validation_error(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch("/api/users/me/password", json={}, headers=auth_header(token))

    assert response.status_code == 422
    missing_fields = {tuple(error["loc"]) for error in response.json()["detail"]}
    assert missing_fields == {("body", "current_password"), ("body", "new_password")}


@pytest.mark.anyio
async def test_change_password_new_password_below_min_length_error(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": PASSWORD, "new_password": "x" * 7},
        headers=auth_header(token),
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "new_password"]
    assert error["type"] == "string_too_short"


@pytest.mark.anyio
async def test_change_password_new_password_over_max_length_error(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": PASSWORD, "new_password": "x" * 129},
        headers=auth_header(token),
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "new_password"]
    assert error["type"] == "string_too_long"


@pytest.mark.anyio
async def test_change_password_clears_outstanding_reset_tokens(
    client: AsyncClient, reset_token: str
):
    token = await login_user(client)

    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": PASSWORD, "new_password": "newpassword123"},
        headers=auth_header(token),
    )
    assert response.status_code == 200

    # independent check: the reset link issued before the change no longer works
    reset_response = await client.post(
        "/api/users/reset-password",
        json={"token": reset_token, "new_password": "anotherpassword123"},
    )
    assert reset_response.status_code == 400
    assert reset_response.json()["detail"] == "This reset link is invalid or has expired."


# * --- GET /api/users/{user_id}: get user -------------------------------------


@pytest.mark.anyio
async def test_get_user_success(client: AsyncClient):
    user = await create_test_user(client)

    response = await client.get(f"/api/users/{user['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user["id"]
    assert data["username"] == "testuser"
    assert data["image_file"] is None
    assert data["image_path"] == "/static/profile_pics/default.jpg"
    # UserPublic, not UserPrivate — a stranger does not get the email
    assert "email" not in data


@pytest.mark.anyio
async def test_get_user_not_found(client: AsyncClient):
    response = await client.get("/api/users/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


# * --- GET /api/users/{user_id}/posts: posts.for_author -----------------------


@pytest.mark.anyio
async def test_get_user_posts_filters_by_author(client: AsyncClient):
    user1 = await create_test_user(client, username="user1", email="user1@example.com")
    token1 = await login_user(client, email="user1@example.com")
    await create_test_post(client, auth_header(token1), title="User1 post")

    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")
    await create_test_post(client, auth_header(token2), title="User2 post")

    response = await client.get(f"/api/users/{user1['id']}/posts")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "User1 post"


@pytest.mark.anyio
async def test_get_user_posts_empty_for_author_with_no_posts(client: AsyncClient):
    user = await create_test_user(client)

    response = await client.get(f"/api/users/{user['id']}/posts")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


# * --- PATCH /api/users/{user_id}: update user --------------------------------


@pytest.mark.anyio
async def test_update_user_username_success(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        f"/api/users/{user['id']}",
        json={"username": "renameduser"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["username"] == "renameduser"


@pytest.mark.anyio
async def test_update_user_password_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    me = await client.get("/api/users/me", headers=auth_header(token))
    user_id = me.json()["id"]

    response = await client.patch(
        f"/api/users/{user_id}",
        json={"password": "newpassword123"},
        headers=auth_header(token),
    )
    assert response.status_code == 200

    # independent check: old password stops working
    old_login = await client.post(
        "/api/users/token", data={"username": "test@example.com", "password": PASSWORD}
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "newpassword123"},
    )
    assert new_login.status_code == 200


@pytest.mark.anyio
async def test_update_user_resend_same_value_accepted(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        f"/api/users/{user['id']}",
        json={"username": "testuser"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["username"] == "testuser"


@pytest.mark.anyio
async def test_update_user_duplicate_username_error(client: AsyncClient):
    await create_test_user(client, username="taken", email="taken@example.com")
    user2 = await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.patch(
        f"/api/users/{user2['id']}",
        json={"username": "taken"},
        headers=auth_header(token2),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username or email already registered"


@pytest.mark.anyio
async def test_update_user_wrong_user_error(client: AsyncClient):
    user1 = await create_test_user(client, username="user1", email="user1@example.com")
    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.patch(
        f"/api/users/{user1['id']}",
        json={"username": "hijacked"},
        headers=auth_header(token2),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to edit profile"


@pytest.mark.anyio
async def test_update_user_unauthorized(client: AsyncClient):
    user = await create_test_user(client)

    response = await client.patch(f"/api/users/{user['id']}", json={"username": "renamed"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_update_user_not_found(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        "/api/users/999", json={"username": "renamed"}, headers=auth_header(token)
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


# * --- DELETE /api/users/{user_id}: delete user --------------------------------
@pytest.mark.anyio
async def test_delete_user_success(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.delete(f"/api/users/{user['id']}", headers=auth_header(token))
    assert response.status_code == 204

    # independent check: the account is really gone
    again = await client.get(f"/api/users/{user['id']}")
    assert again.status_code == 404


@pytest.mark.anyio
async def test_delete_user_cascades_posts(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)
    post = await create_test_post(client, auth_header(token))

    response = await client.delete(f"/api/users/{user['id']}", headers=auth_header(token))
    assert response.status_code == 204

    # independent check: the post did not survive its author
    again = await client.get(f"/api/posts/{post['id']}")
    assert again.status_code == 404


@pytest.mark.anyio
async def test_delete_user_removes_avatar_from_storage(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    test_image_path = Path(__file__).parent / "test_image.jpg"
    await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(test_image_path.read_bytes()), "image/jpeg")},
        headers=auth_header(token),
    )

    response = await client.delete(f"/api/users/{user['id']}", headers=auth_header(token))
    assert response.status_code == 204

    # independent check: the file is gone from the mocked bucket, not just the row
    s3_object = mocked_aws.list_objects_v2(Bucket=S3_BUCKET_NAME)
    assert "Contents" not in s3_object


@pytest.mark.anyio
async def test_delete_user_wrong_user_error(client: AsyncClient):
    user1 = await create_test_user(client, username="user1", email="user1@example.com")
    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.delete(f"/api/users/{user1['id']}", headers=auth_header(token2))

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to edit profile"


@pytest.mark.anyio
async def test_delete_user_unauthorized(client: AsyncClient):
    user = await create_test_user(client)

    response = await client.delete(f"/api/users/{user['id']}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_delete_user_not_found(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.delete("/api/users/999", headers=auth_header(token))

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


# * --- PATCH /api/users/{user_id}/picture: upload avatar ---------------------


@pytest.mark.anyio
async def test_upload_profile_picture(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    test_image_path = Path(__file__).parent / "test_image.jpg"
    image_bytes = test_image_path.read_bytes()

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(image_bytes), "image/jpeg")},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["image_file"] is not None
    assert data["image_file"].endswith("jpg")
    assert "s3" in data["image_path"]

    s3_object = mocked_aws.list_objects_v2(Bucket=S3_BUCKET_NAME)
    assert "Contents" in s3_object
    assert len(s3_object["Contents"]) == 1
    assert s3_object["Contents"][0]["Key"].endswith(data["image_file"])


@pytest.mark.anyio
async def test_upload_profile_picture_too_large_error(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    oversized = b"x" * (settings.max_upload_size_bytes + 1)

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(oversized), "image/jpeg")},
        headers=auth_header(token),
    )

    assert response.status_code == 400
    megabytes = settings.max_upload_size_bytes // (1024 * 1024)
    assert response.json()["detail"] == f"File is too large. Maximum size is {megabytes} MB"

    # independent check: a rejected upload never reaches storage
    s3_object = mocked_aws.list_objects_v2(Bucket=S3_BUCKET_NAME)
    assert "Contents" not in s3_object


@pytest.mark.anyio
async def test_upload_profile_picture_not_an_image_error(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("notes.txt", BytesIO(b"this is plain text, not an image"), "text/plain")},
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Invalid image file. Please upload a valid file format (JPEG, PNG, GIF, WebP)."
    )

    s3_object = mocked_aws.list_objects_v2(Bucket=S3_BUCKET_NAME)
    assert "Contents" not in s3_object


# * --- DELETE /api/users/{user_id}/picture: remove avatar ---------------------
@pytest.mark.anyio
async def test_delete_profile_picture_success(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    test_image_path = Path(__file__).parent / "test_image.jpg"
    await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(test_image_path.read_bytes()), "image/jpeg")},
        headers=auth_header(token),
    )

    response = await client.delete(f"/api/users/{user['id']}/picture", headers=auth_header(token))

    assert response.status_code == 200
    data = response.json()
    assert data["image_file"] is None
    assert data["image_path"] == "/static/profile_pics/default.jpg"

    # independent check: the file is gone from the mocked bucket
    s3_object = mocked_aws.list_objects_v2(Bucket=S3_BUCKET_NAME)
    assert "Contents" not in s3_object


@pytest.mark.anyio
async def test_delete_profile_picture_no_picture_error(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.delete(f"/api/users/{user['id']}/picture", headers=auth_header(token))

    assert response.status_code == 400
    assert response.json()["detail"] == "No picture to delete."


@pytest.mark.anyio
async def test_delete_profile_picture_wrong_user_error(client: AsyncClient):
    user1 = await create_test_user(client, username="user1", email="user1@example.com")
    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.delete(f"/api/users/{user1['id']}/picture", headers=auth_header(token2))

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to edit profile"


@pytest.mark.anyio
async def test_delete_profile_picture_unauthorized(client: AsyncClient):
    user = await create_test_user(client)

    response = await client.delete(f"/api/users/{user['id']}/picture")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_delete_profile_picture_not_found(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.delete("/api/users/999/picture", headers=auth_header(token))

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


# * --- services.users: IntegrityError race guard -------------------------------
# Can't be exercised as a real race: one db_session per test, not safe for
# concurrent use. Instead patch commit() to raise the same exception a real
# unique-index collision would, and check it becomes a clean 400, not a 500.
@pytest.mark.anyio
async def test_register_race_condition_becomes_already_registered(db_session: AsyncSession):
    with (
        patch.object(
            db_session,
            "commit",
            AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("unique violation"))),
        ),
        pytest.raises(users.AlreadyRegistered) as exc_info,
    ):
        await users.register(
            db_session,
            UserCreate(username="raceuser", email="race@example.com", password="password123"),
        )

    assert exc_info.value.detail == "Username or email already registered"


@pytest.mark.anyio
async def test_update_user_race_condition_becomes_already_registered(
    client: AsyncClient, db_session: AsyncSession
):
    user = await create_test_user(client)
    row = await db_session.get(models.User, user["id"])
    assert row is not None

    with (
        patch.object(
            db_session,
            "commit",
            AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("unique violation"))),
        ),
        pytest.raises(users.AlreadyRegistered) as exc_info,
    ):
        await users.update(db_session, row, UserUpdate(username="racedname"))

    assert exc_info.value.detail == "Username or email already registered"
