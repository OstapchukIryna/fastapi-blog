# fastapi-blog

A small blog: posts with tags, accounts with avatars, a JSON API and a set of
server-rendered pages over the same PostgreSQL data.

This is also a work sample. The code here is what gets judged, not a
description of work done somewhere else.

## Stack

- FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic
- PostgreSQL
- Jinja2 for the server-rendered pages
- Argon2 for passwords, JWT for sessions, S3 for avatars
- pytest against a real Postgres database, a Postman/Newman contract suite
  for the JSON API

## Running it

Needs a `.env` in the repository root with at least `DATABASE_URL`,
`SECRET_KEY` and `S3_BUCKET_NAME` — the full list of settings, with their
defaults, is `src/blog/core/config.py`.

```bash
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env
uv sync
uv run alembic upgrade head
uv run uvicorn blog.main:app --reload
```

## Testing

```bash
uv run pytest                                    # in-process, against a throwaway Postgres DB
uv run pytest tests/test_import_graph.py         # layering/cycle rules only, no DB needed
./scripts/api-tests.sh                           # Postman collection, throwaway DB
uv run ruff check .
uv run pyrefly check src/blog tests scripts
```

## Layout

Five layers under `src/blog/`, each importing only downward or sideways:

```
core            settings, JWT/password crypto
infrastructure  database engine, ORM models, S3, email
schemas         pydantic shapes at the boundary
services        what can be done, and under what conditions
presentation    api/ (JSON) and web/ (Jinja pages), neither importing the other
```

`tests/test_import_graph.py` enforces this by walking the actual import graph:
an edge pointing the wrong way fails the test, not just the review.
