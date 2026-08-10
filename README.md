# fastapi-blog

A small blog: posts with tags, accounts with avatars, a REST API architecture with a set of
server-rendered pages over the PostgreSQL database with migration via Alembic.

## Stack

- FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic
- PostgreSQL
- Jinja2 for the server-rendered pages
- Argon2 for passwords, JWT for sessions, S3 for storing avatars
- pytest against a Postgres database, a Postman tests for API

## Testing

```bash
uv run pytest                                    # in-process, against a throwaway Postgres DB
uv run pytest tests/test_import_graph.py         # layering/import cycle rules
./scripts/api-tests.sh                           # Postman collection
uv run ruff check .
uv run pyrefly check src/blog tests scripts
```

## Layout

Five layers under `src/blog/`, each importing only downward or sideways; all of them have a strongly downward importing and no leaks of into highest levels of modules:

```
core            settings, JWT/password crypto
infrastructure  database engine, ORM models, S3, email
schemas         pydantic shapes at the boundary
services        core business-logic and conditions
presentation    api/ (JSON) and web/ (Jinja pages)
```

`tests/test_import_graph.py` enforces this by walking through import graph
