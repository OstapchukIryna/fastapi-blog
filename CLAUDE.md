# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small FastAPI blog: posts with tags, accounts with avatars, a JSON API and a
set of server-rendered pages over the same PostgreSQL data. It is also a work
sample — see `PRODUCT.md` for who it's for and `DESIGN.md` for the visual
system. Deep architecture docs already exist under `docs/` (see below); this
file is the short version plus things that aren't written down anywhere else.

## Commands

```bash
# Setup
cp .env.example .env
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env
uv sync
uv run alembic upgrade head             # schema
uv run python seed.py                   # five real posts (idempotent)

# Run
uv run uvicorn blog.main:app --reload

# Lint / types / docs
uv run ruff check .
uv run ruff format --check src seed.py populate.py tests scripts
uv run djlint templates/ --check
uv run pyrefly check src/blog seed.py populate.py tests scripts
uv run mkdocs build --strict            # docs must build clean too

# Tests
uv run pytest                                    # all three browser journeys
uv run pytest tests/test_browser.py::test_name   # a single test
uv run pytest tests/test_import_graph.py         # layering/cycle rules only, no browser needed
./scripts/api-tests.sh                           # Postman collection, throwaway DB
uv sync --locked                                 # fails if uv.lock drifted from pyproject.toml

# Migrations
uv run alembic revision --autogenerate -m "..."
uv run alembic check                             # fails if a model edit has no migration
```

Tests need PostgreSQL, not SQLite — `conftest.py` derives a throwaway database
by suffixing `_test` onto `DATABASE_URL` (or reads `TEST_DATABASE_URL`), drops
and recreates its schema every session via `alembic upgrade head`, then runs
`seed.py`. `blog.db` / your dev database are never touched. First run on a
machine also needs `uv run playwright install chromium`.

## Architecture

Five layers under `src/blog/`, each a package, imports pointing only down or
sideways — never up. `tests/test_import_graph.py` enforces this by walking the
actual AST (not `docs/architecture.md`, which the test's docstring says it
exists to keep honest): any upward edge fails, and any sideways edge must be
declared in that file's `ALLOWED_SIDEWAYS` with a reason.

```
core            settings, JWT/password crypto — imports nothing of ours
infrastructure  engine, ORM models, disk/email
schemas         Pydantic shapes at the boundary (incl. shared Pagination/Page[T])
services        what can be done and under what conditions (CurrentUser, OwnedPost, ...)
presentation    api/ (JSON, /api/v1/...) and web/ (Jinja pages) — siblings, neither imports the other
```

`presentation/web` and `presentation/api` both depend on `services`, never on
each other — that's what keeps a "post not found" check in one place. Two
import cycles have happened in this project's history, both from a
sideways-looking helper (tag cleanup, then pagination) that was actually
shared vocabulary and belonged a layer down instead of next to one of its
users. Ask the same question before adding a new same-layer import: *if
neither module existed, would the other still make sense?* If yes, push it
down a layer; if no, it's a real dependency — declare it.

Two protocols invert the direction of `infrastructure`/`api` depending on
`services`: `AvatarStorage` (declared in `services/avatars.py`, satisfied by
`infrastructure/images.py`) and `ResetMailer` (declared in
`services/passwords.py`, satisfied by `presentation/api/mail.py`). Structural
typing (`Protocol`, not `ABC`) is what lets the implementation avoid importing
the interface — an `ABC` would need inheritance, which would need the import,
which the layering test forbids.

Two front doors onto the same services: `presentation/web/pages/` (18 routes,
`include_in_schema=False`, so `/openapi.json` — and the Postman contract test
built from it — describes only the 13 JSON paths) and `presentation/api/`
under `API_PREFIX = "/api/v1"`. Sign-in, registration and the profile page
render as empty shells whose own JS calls the JSON API, because the token
lives in `localStorage`, which Jinja cannot see; every other page is rendered
server-side, whole.

For depth beyond this file: `docs/architecture.md` (import graph, ER diagram,
browser-JS graph, all generated from code), `docs/auth.md` (dependency
resolution order — which refusal wins when several apply), `docs/adr-001-pages-and-api.md`,
`docs/conventions.md` (comment markers, docstring style, Protocol rules).

## Gotchas

- **`blog.main:app`, not `src.blog.main:app`.** Both import — `src` works as
  a namespace package from the repo root — but they build two different
  `FastAPI` objects. Models stay shared because every internal import is
  absolute (`blog....`), which is what makes the duplication quiet instead of
  an obvious error. Always use `blog.main:app` (see the `[tool.fastapi]`
  comment in `pyproject.toml`).
- **`except TypeError, ValueError:`** (in `services/auth.py`) is not a
  leftover Python 2 pattern — it's PEP 758's unparenthesized multi-exception
  syntax, valid because this project requires Python 3.14+. Don't "fix" it by
  wrapping in parens or reading it as buggy.
- **Dependency type aliases must stay real imports, never `TYPE_CHECKING`.**
  `DbSession`, `CurrentUser`, `OwnedPost`, etc. are `Annotated[X, Depends(...)]`
  values FastAPI resolves at runtime. Hiding the import under
  `TYPE_CHECKING` doesn't error — the parameter silently becomes a query
  param and the route starts answering 422 with nothing informative in the
  log. This is why `TC001`/`TC002`/`TC003` are disabled repo-wide in
  `pyproject.toml`.
- **Settings come from `blog.core.config.settings`, not `os.getenv`.**
  `.env` is read by pydantic-settings and is not in the process environment,
  so reading the environment directly "works" in the app but silently sees
  nothing in scripts/tests that do it themselves.
- **Argon2 only.** `pwdlib`'s hasher raises on a hash it doesn't recognize
  (e.g. a stray bcrypt hash) rather than returning "no match" — anything
  writing `users.password_hash` must go through `hash_password`.
- **Colors change only through the CSS custom properties** in `:root` and
  `[data-bs-theme]` (see `DESIGN.md`). A hardcoded hex value in a template or
  stylesheet can't follow a theme switch.
- **`is_pinned` has no DB constraint** — `services/posts.set_pinned` clears
  the other rows in the same transaction; nothing stops two pins if written
  another way.
