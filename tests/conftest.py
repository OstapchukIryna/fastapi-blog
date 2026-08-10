import os
from collections.abc import AsyncGenerator

SECRET_KEY = "test-secret-key-for-tests-only-32-bytes-plus"
DATABASE_URL = "postgresql+psycopg://bloguser:blogpassword@localhost/test_blog"
S3_BUCKET_NAME = "test_bucket"
S3_ACCESS_KEY = "testing"
S3_REGION = "eu-north-1"

PASSWORD = "correct-horse-battery"

os.environ["DATABASE_URL"] = DATABASE_URL
os.environ["S3_BUCKET_NAME"] = S3_BUCKET_NAME
os.environ["SECRET_KEY"] = SECRET_KEY


# Dummy S3/AWS credentials
os.environ["S3_ACCESS_KEY_ID"] = S3_ACCESS_KEY
os.environ["S3_SECRET_ACCESS_KEY"] = S3_ACCESS_KEY
os.environ["S3_REGION"] = S3_REGION

# Boto3 has its own credentials
os.environ["AWS_ACCESS_KEY_ID"] = S3_ACCESS_KEY
os.environ["AWS_SECRET_ACCESS_KEY"] = S3_ACCESS_KEY
os.environ["AWS_DEFAULT_REGION"] = S3_REGION


# When all important vars are overwritten, we can safely do imports
# ! Order matters a lot (with pydantic)!

import boto3
import pytest
from httpx import ASGITransport, AsyncClient
from moto import mock_aws
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from blog.core.rate_limit import limiter
from blog.infrastructure import database
from blog.infrastructure.database import Base, get_db
from blog.main import app

# Tells pytest that we test async func so add it in an event loop
pytest_plugins = ["anyio"]


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


## Creates test db engine
@pytest.fixture(scope="session")
def test_engine():
    engine = create_async_engine(
        os.environ["DATABASE_URL"], poolclass=NullPool
    )  # disables connection pooling entirely
    return engine


## Setup database
@pytest.fixture(scope="session")
async def setup_database(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


## ! DB Session with rollback
# * This is function-scope, so every test use separate session
@pytest.fixture
async def db_session(test_engine, setup_database) -> AsyncGenerator[AsyncSession]:
    conn = await test_engine.connect()
    trans = await conn.begin()

    # Bound to the specific connection, not an engine
    test_async_session = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",  # fake commit method
    )

    # Every test request a session and fixture rollback all its changes after
    async with test_async_session() as session:
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
            await conn.close()


## Mocked AWS
@pytest.fixture
def mocked_aws():
    with mock_aws():
        s3 = boto3.client("s3", region_name=S3_REGION)
        s3.create_bucket(
            Bucket=S3_BUCKET_NAME,
            CreateBucketConfiguration={"LocationConstraint": S3_REGION},
        )
        yield s3


@pytest.fixture
async def client(db_session: AsyncSession, mocked_aws) -> AsyncGenerator[AsyncClient]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # The limiter's in-memory bucket is a module-level singleton and would
    # otherwise carry counts over from whichever test ran before this one -
    # every test starts under the same fake IP address.
    limiter.reset()
    # ASGITransport does not run the app's lifespan, so nothing else ever
    # calls setup_engine() in tests - only /api/health needs it (its own
    # connection, deliberately outside get_db's override above).
    database.setup_engine()
    # Asynchronous Server Gateway Interface mocks real server invoke
    async with (
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",  # we are not using the real web calls, but url requires for proper behavior
        ) as ac
    ):
        yield ac

    await database.teardown_engine()
    app.dependency_overrides.clear()


async def create_test_user(
    client: AsyncClient,
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = PASSWORD,
):
    response = await client.post(
        "/api/users",
        json={"username": username, "email": email, "password": password},
    )

    assert response.status_code == 201, f"Failed to create user: {response.text}"
    return response.json()


async def login_user(
    client: AsyncClient, email: str = "test@example.com", password: str = PASSWORD
) -> str:
    response = await client.post(
        "/api/users/token",
        data={
            "username": email,
            "password": password,
        },  # ! OAuth requires data, not a json
    )
    assert response.status_code == 200, f"Failed to login: {response.text}"
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_test_post(
    client: AsyncClient,
    headers: dict[str, str],
    title: str = "my first post",
    summary: str = "a short summary",
    content: str = "this is content",
    tags: list[str] | None = None,
):
    payload = {"title": title, "summary": summary, "content": content}
    if tags is not None:
        payload = {**payload, "tags": tags}

    response = await client.post("/api/posts", json=payload, headers=headers)
    assert response.status_code == 201, f"Failed to create post: {response.text}"
    return response.json()
