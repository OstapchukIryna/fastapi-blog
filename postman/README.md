# API tests

The Postman collection for the JSON API, and the script that runs it
without a browser.

```
postman/
  collections/fastapi-blog.postman_collection.json   27 requests, 152 assertions
  environments/local.postman_environment.json        just baseUrl
```

## Running it

```bash
./scripts/api-tests.sh
```

That seeds a throwaway database in a temp directory, starts the app
against it, runs the collection with Newman, and tears everything down.
`blog.db` is committed, so nothing in an automated run may write to it —
the CI job asserts that afterwards with `git diff --exit-code`.

Newman is fetched by `npx` on demand; there is no `package.json` and
nothing to install. Node is the only requirement beyond the Python
toolchain.

Against a server that is already up:

```bash
./scripts/api-tests.sh --url http://127.0.0.1:8000
```

Inside Postman, import both files and pick the **fastapi-blog local**
environment. The run is self-contained — it creates its own user, works
through that user's post, and deletes the user at the end, so it can be
run repeatedly against the same database.

## What the tests actually check

Status codes are the least of it. Each request asserts the behaviour the
routers document, so the collection fails when the documented contract
changes rather than when the API merely moves:

- `PATCH` leaves absent fields alone, and an empty body is a legitimate
  no-op rather than an error.
- `PUT` replaces every field, which is the only thing separating it from
  `PATCH`.
- Tags are trimmed, lowercased and de-duplicated with order preserved,
  and are replaced wholesale — so `[]` clears them while omitting the key
  keeps them.
- A second `DELETE` is a 404, not a 204. The effect is idempotent; the
  report is honest.
- A duplicate username is a 400 rather than the 500 a raw constraint
  violation would produce.
- The list endpoint returns `PostResponse` and carries no body text; only
  the detail endpoint adds `content`.
- A user response never contains the password or its hash.
- The 422 body keeps the `loc` / `type` / `ctx` shape that
  `static/js/utils.js` reads to put messages under the right form field.
  That is a contract between the API and the browser, and nothing else
  tests it.

The first request in the run compares the paths in `/openapi.json`
against the paths this collection covers, and fails when they diverge.
Adding an endpoint without adding requests for it breaks the build,
which is the only way "the collection covers the API" stays true.

There is no committed copy of the OpenAPI spec. FastAPI generates it from
the routers, so a snapshot in this directory could only ever be a second
source that goes stale — the coverage test above is the check that a
snapshot would pretend to be. To load the live spec into Postman's Spec
Hub:

```bash
uv run python -c "import json, main; print(json.dumps(main.app.openapi(), indent=2))" > /tmp/openapi.json
```

## Known contract wart

`date_posted` comes back with a `Z` suffix from `POST /api/posts` and
without one from every other endpoint. On create the value is still the
timezone-aware object in memory; everywhere else it is read back from
SQLite, which has no timezone type and returns it naive. A client parsing
the field gets UTC on create and an ambiguous local-looking timestamp on
every subsequent read.

The tests assert only that the field parses, so they pass either way.
Fixing it properly means storing UTC explicitly and serialising it the
same way on every route.

## Where this sits relative to pytest

These are contract tests: they exercise the API over HTTP the way a
client does, and they need a running server. They do not replace unit
tests — nothing here reaches inside a function, and a collection cannot
tell you which branch was not taken. When pytest arrives, the sensible
split is unit and integration tests there, this collection kept for the
contract and for the parts that are easier to read as requests than as
fixtures.
