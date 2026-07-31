# API tests

The Postman collection for the JSON API, and the script that runs it
without a browser.

51 requests, 289 assertions, in Postman's own on-disk format — one YAML
file per request, so a changed test reads as a change in review rather
than as a line moving inside a JSON blob.

```
postman/
  collections/fastapi-blog API/
    Contract/         the spec covers what this collection covers   (1)
    Users/            registration, sign-in, reading, updating     (10)
    Auth/             every way a token is accepted or refused     (13)
    Posts/            the life of a post                           (12)
    Tags/             the tag index and its ordering                (3)
    Authorization/    signed in, and still not allowed              (9)
    Cleanup/          removes the three accounts a run creates      (3)
  environments/fastapi-blog local.environment.yaml    just baseUrl
```

Newman reads a single-file v2.1 JSON, which `scripts/api-tests.sh`
builds from this tree on each run and throws away afterwards. It is not
committed: a second copy would be a second thing to keep in step.

## Running it

```bash
./scripts/api-tests.sh
```

That seeds a throwaway database in a temp directory, starts the app
against it, runs the collection with Newman, and tears everything down.
`blog.db` is committed, so the run must not write to it — `git status`
after a run should be clean, and that is worth glancing at.

Nothing runs this automatically at the moment. There is no CI workflow
in the repository: the old one checked lint and this collection, and was
removed until a proper one is set up alongside pytest. Until then this
is a command to run by hand before pushing.

Newman is fetched by `npx` on demand; there is no `package.json` and
nothing to install. Node is the only requirement beyond the Python
toolchain.

Against a server that is already up:

```bash
./scripts/api-tests.sh --url http://127.0.0.1:8000
```

Inside Postman, open the workspace and pick the **fastapi-blog local**
environment. The run is self-contained — it creates its own accounts,
works through their posts, and removes them at the end, so it can be run
repeatedly against the same database. `git status` after a run is the
check that this stayed true.

One environment variable beyond `baseUrl`: `jwtSecret`, which the script
passes from the server it starts. Four tests in **Auth** mint their own
tokens with it, which is the only way to produce one that is expired, or
missing a required claim, on purpose. Without it those four still assert
a 401, but for the wrong reason — they become forged-signature tests.

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
- Signing in is refused the same way for a wrong password and for an
  address nobody registered, so the response cannot be used to find out
  which addresses exist.
- A token is refused when it is expired, forged, missing `exp`, missing
  `sub`, announced with the wrong scheme, or belongs to an account that
  has since been deleted — and each of those is asserted separately,
  because they fail for different reasons in different lines of code.
- Being signed in is not being allowed: another account is refused with
  403, not 401, on every write to a post or a profile it does not own —
  and a following request checks the post and the password were really
  left alone, since a status code says what the API answered, not what
  it did first.
- Every protected endpoint refuses an anonymous caller, and every public
  one still answers without an account. Reading this blog must not need
  one, and locking down a router is a line away from breaking that.
- A duplicate username is a 400 rather than the 500 a raw constraint
  violation would produce.
- The list endpoint returns `PostResponse` and carries no body text; only
  the detail endpoint adds `content`.
- A user response never contains the password or its hash.
- The 422 body keeps the `loc` / `type` / `ctx` shape that
  `static/js/utils.js` reads to put messages under the right form field.
  That is a contract between the API and the browser, and nothing else
  tests it.

The order those refusals happen in — which one wins when more than one
applies — is drawn out in [`docs/auth.md`](../docs/auth.md). Every row
of its precedence table is a request in this collection.

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
