# fastapi-blog

A small blogging application: posts with tags, accounts with avatars, a
JSON API and a set of server-rendered pages over the same data.

This site is the reasoning, not the tutorial. The code says what happens;
these pages say why it happens that way, and what went wrong before it
did.

## Where to start

| If you want to know | Read |
|---|---|
| what may import what, and why | [The shape of this application](architecture.md) |
| how a request proves who it is | [How a request is authenticated](auth.md) |
| why the pages have their own router | [ADR-001](adr-001-pages-and-api.md) |
| how the code is annotated | [Conventions](conventions.md) |
| what a specific function does | [Reference](reference/core.md) |

## Running it

```bash
cp .env.example .env
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env
uv sync
uv run python seed.py                  # five real posts
uv run uvicorn blog.main:app --reload
```

`seed.py` is idempotent and small. For enough records to see pagination
work, `populate.py --yes` creates six authors and 45 posts — it is
destructive, and says so before it acts.

## Checking it

Every one of these runs on every pull request; see
`.github/workflows/ci.yml`. Running them locally first is faster than
waiting for the answer.

```bash
uv run ruff check . && uv run pyrefly check src/blog seed.py populate.py tests scripts
uv run pytest                # in-process, against Postgres, plus the import-graph rules
./scripts/api-tests.sh       # the Postman collection against a throwaway database
uv run mkdocs serve          # this site, with live reload
uv sync --locked             # fails if uv.lock has drifted from pyproject
```

The pipeline is three parallel jobs: **static** (ruff, djlint, pyrefly,
a strict docs build and the lockfile check), **tests** (pytest against a
throwaway Postgres database), and **API contract** (the Postman collection
against a throwaway database). On master, a fourth workflow publishes this
site.

## The shape of it in one paragraph

Five layers, each a package under `src/blog/`: `core` (settings,
cryptography), `infrastructure` (engine, ORM classes, disk), `schemas`
(the shapes at the boundary), `services` (what can be done and on what
conditions), `presentation` (`api/` for JSON, `web/` for pages). Imports
point down or sideways, never up, and a test enforces that rather than a
convention remembering to.
