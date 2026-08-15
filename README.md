# fastapi-blog

A blog with a REST API and server-rendered pages with PostgreSQL
database. List of posts and tags, users' profiles.

Built as a work sample. There is no commercial project behind it, so the
code is the thing to look at.


## Running it locally

Needs Python 3.14, PostgreSQL, [uv](https://docs.astral.sh/uv/), and an
S3 bucket for avatars.

Configuration comes from `.env` in the repository root.

```bash
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env

uv sync
uv run alembic upgrade head
uv run uvicorn blog.main:app --reload
```

## Layout

Five layers under `src/blog/`, each importing only downward or sideways:

```
core            settings, password hashing, JWT
infrastructure  database engine, ORM models, S3, email
schemas         Pydantic models at the boundary
services        core business logic and conditions
presentation    api/ (JSON) and web/ (Jinja pages)
```

`tests/test_import_graph.py` walks the real import graph, so an import
pointing the wrong way fails the test rather than waiting for review.

Two conventions follow from the split:

- **Transactions belong to services.** A function that changes something
  commits it, so saving is never two calls a caller has to remember to
  make in order.
- **Services return ORM objects, not response models.** The JSON routes
  wrap them in a schema; the pages read attributes off them directly.

## Testing

```bash
uv run pytest                              # against a throwaway Postgres database
uv run pytest tests/test_import_graph.py   # layering rules only, no database needed
./scripts/api-tests.sh                     # Postman collection, throwaway database

uv run ruff check .
uv run pyrefly check src/blog tests scripts
```

Tests run against PostgreSQL database and not SQLite.
Each test gets its own transaction, rolled back afterwards.

## Notes

- Passwords are hashed with Argon2. Reset tokens are random, stored as a
  SHA-256 hash and single-use.
- Sessions are stateless JWTs. Changing a password invalidates the tokens
  issued before it, by comparing the token's `iat` against the account's
  `password_changed_at`.
- Sign-in answers the same way for an unknown address, a wrong password
  and a locked account — and takes the same time to do it.
- Repeated failures lock an account for a doubling interval.
- Uploaded images are re-encoded to a fixed-size JPEG before storage, and
  read in chunks so an oversized upload is refused before it is in memory.
