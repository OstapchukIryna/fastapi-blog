# What is worth testing, and why

Eighty-four invariants, collected by reading the source rather than by
brainstorming. Every row is a claim the code already makes about itself, in a
docstring or behind a `# *` / `# !` marker. Nothing here was invented for this
document: the comments were written at the moment each decision was made, which
means the hard part of writing a test plan — knowing which behaviour is load-
bearing and which is incidental — was already done and only needed collecting.
That is the return on the comment convention, arriving later than expected and
somewhere else.

The **Prevents** column is the point of the row. A test whose failure message
does not tell you what broke in the product is a test that will be deleted the
first time it is inconvenient. Where the column says *«already happened»*, the
bug is recorded in a commit message or a source comment: those are regressions,
not hypotheses, and they are the rows to write first.

## What exists now

| Suite | Covers | Count |
|---|---|---|
| `tests/test_import_graph.py` | layering: no cycles, no upward arrows, every sideways arrow declared, the app imports for real | 4 tests |
| `tests/test_browser.py` | register → sign in → publish, expiry noticed on the profile, edit offered to the author only | 3 tests |
| `postman/` via `scripts/api-tests.sh` | the JSON surface end to end | 375 assertions |

What that leaves uncovered is a shape, not a list: **the layer where the rules
live has nothing pointed at it directly.** Postman reaches `services/` through
HTTP, so a rule is exercised only in the combinations some endpoint happens to
produce, and a failure names the endpoint rather than the rule. Boundaries —
`has_more` at exactly the last row, `normalise_tags` on `["", " "]` — are
awkward to reach that way and trivial to reach directly.

## Fixtures to build first

These block most of the plan, and none of them exist yet. `conftest.py` today
has `live_server` (a subprocess against a seeded throwaway database), `api`,
`make_account`, `sign_in` and `expired_token` — all of them shaped for driving
a real browser.

| Fixture | What it gives | Notes |
|---|---|---|
| `session` | an `AsyncSession` against `sqlite+aiosqlite:///:memory:`, schema created, rolled back after each test | unlocks every `db`-level row below. Needs `pytest-asyncio` (or `anyio`), which is not a dependency yet |
| `client` | `httpx.AsyncClient` over `ASGITransport(app=app)`, no subprocess | in-process, so `dependency_overrides` works and a test can assert on a service call |
| `avatars` | `DiskAvatars(directory=tmp_path)` wired in through `app.dependency_overrides[get_avatar_storage]` | this is what `AvatarStorage` was extracted for; keeps images off the repository |
| `mailer` | a recording `ResetMailer` — appends `(to_email, username, token)` instead of sending | makes the reset token readable without SMTP or a background task |
| `author` | a user with N posts, one pinned, known tags | most `db` rows below need a fixed corpus, and `seed.py` is too coarse |

`settings` is read at import time, so a test that needs different settings must
set the environment before `blog.core.config` is imported. That is why
`live_server` spawns a subprocess. An in-process `client` fixture works for
everything that does not need to *change* settings.

!!! note "Coverage"

    `pytest-cov` is not a dependency yet. When it is added, protocol and
    exception-class bodies are already docstrings rather than `...`, so they
    will not show up as permanently missed lines — see
    [Protocols, not abstract base classes](conventions.md#protocols-not-abstract-base-classes).

---

## 1. Pagination and ordering

The quietest failures in the project. Nothing raises; a reader is simply shown
a post twice and another never.

| Invariant | Prevents | Level |
|---|---|---|
| `base_query` orders by `is_pinned desc, date_posted desc, id desc` — a **total** order | two posts sharing a second swap places between requests, so one appears on two consecutive pages and another on none. *Already happened* | `db` |
| `_slice` counts through the query it was given, not the table | an author's page reporting every post there is, leaving "load more" visible after the last row. *Already happened* | `db` |
| `Page.has_more` is `skip + len(items) < total` | off-by-one at the boundary: a button that fetches an empty batch, or one that hides the last record. Test at `total-1`, `total`, `total+1` | `unit` |
| `Feed.more` is `shown < total`, and `shown` is `skip + len(items)` | the same boundary, computed a second time for the HTML surface — the two must agree | `unit` |
| `limit` is refused above `MAX_PAGE_SIZE` (100) | one request with `limit=100000` pulling the whole table, every row joined to its author | `unit` |
| `skip >= 0`, `limit >= 1` | a negative offset reaching the database | `unit` |
| `Page.of` echoes the request's own `skip`/`limit` back | a client having to remember what it asked for | `unit` |
| `tags.with_counts` breaks ties by name after count | same swap as above, on the topics page | `db` |
| `tags.with_counts` counts the same subquery it selects from | orphan tags inflating the total, so "load more" outlives the last tag | `db` |
| `selectinload` for tags, `joinedload` for the author | `joinedload` on a collection makes `LIMIT` slice join rows instead of posts — a page asking for ten shows four | `db` |
| `arrange` reads `items[0]` rather than scanning for `is_pinned` | on batch two the pinned post is not in the slice, so a scan finds nothing and an arbitrary post takes the lead position. *Already happened* | `unit` |
| `arrange` reports `pinned=None` when the lead is not actually pinned | the hero treatment given to whatever sorted first | `unit` |

## 2. Nothing reveals who has an account

The project's strongest security property, and the one most spread out — four
call sites have to agree, and no single test covers the agreement.

| Invariant | Prevents | Level |
|---|---|---|
| `auth.authenticate` raises the **same** `Unauthorized`, same message and status, for an unknown email and for a wrong password | a 404 for an unknown address and a 401 for a wrong one answers "does this person have an account here" to anyone who asks | `db` |
| `POST /users/forgot-password` answers 202 with a byte-identical body for a known and an unknown address | the form becoming an address oracle. Assert the responses are **equal**, not merely both 202 | `api` |
| `passwords.request_reset` returns `None` in both cases | any future caller regaining a value to branch on | `db` |
| `AlreadyRegistered` names neither field | "username or email already registered" narrowing to which | `unit` |
| `InvalidResetToken` is one message for unknown, expired, spent, and deleted-account | somebody holding a guess learning it was close | `db` |
| `WrongPassword` is a *distinct* message from the reset refusal | the deliberate asymmetry being "fixed" into uniformity — here the caller is already signed in, so nothing is revealed and specificity is a kindness | `unit` |
| `UserPublic` carries no `email`; only `UserPrivate` does | an address leaving through an endpoint that never established who is asking. Test the schema, not the route: that is where it is enforced | `unit` |
| the database stores only `hash_reset_token(token)`, never the token | a reader of the database being able to use what they find | `db` |
| `/reset-password` (the page) does not read the token server-side | the token in access logs and in the `Referer` of anything the page loads | `api` |

## 3. Transactions and ordering of effects

Every row here is "the file outlives the transaction, or does not".

| Invariant | Prevents | Level |
|---|---|---|
| `set_pinned` clears the previous winner and sets the new one in **one** transaction | two pinned posts, or none, if the second write fails. A constraint cannot do this — it can only reject the second write, not perform the first | `db` |
| `avatars.set_picture` deletes the old file **after** the commit | a failed transaction leaving a live row pointing at a filename that is gone | `db` |
| `users.delete` deletes the file after the commit, and reads the filename before | the same, plus an orphan file nothing references | `db` |
| `tags.get_or_create` stages but does not commit | tags surviving a post that failed to save | `db` |
| `register` turns a racing `IntegrityError` into `AlreadyRegistered` after a rollback | a 500 for two people registering the same name at once | `db` |
| `update` does the same | as above, on an edit | `db` |
| `get_db` discards uncommitted work when the request ends | a service that raises midway leaving half a change behind | `api` |
| `expire_on_commit=False` — attributes are readable after commit | an attribute read in a template triggering IO with no session to do it in, failing a long way from the commit that caused it | `db` |
| deleting a user cascades to posts **and** reset tokens | an orphaned post with no author to display; a live token pointing at nothing | `db` |
| deleting a post removes its `post_tags` rows and leaves the tags | broken links, or tags vanishing from under other posts | `db` |

## 4. PUT is not PATCH

| Invariant | Prevents | Level |
|---|---|---|
| `posts.replace` dumps **without** `exclude_unset` — an omitted field takes the model default | PUT quietly behaving like PATCH, making the two endpoints identical | `db` |
| `posts.update` uses `exclude_unset` + `exclude_none` — omitted and `null` both mean "leave alone" | a null clearing a non-nullable column | `db` |
| `PostUpdate.clean_tags` passes `None` through as `None` | the distinction the whole model rests on dying in validation: `tags=[]` clears, omitted keeps | `unit` |
| `posts.update` with an empty body changes nothing and returns the post | an empty PATCH being an error, or worse, a wipe | `db` |
| `users.update` never lets a password reach the model as typed | a plaintext password in the database | `db` |
| `_already_taken` does not count re-sending a value you already hold | a no-op edit failing as a clash with yourself | `db` |
| `_already_taken` considers only `username` and `email` | a pointless query per edit, or a false clash on a non-unique column | `db` |
| `users.update` lower-cases `email` on write | the unique index being slipped past by a different capitalisation | `db` |
| `own_account` and `owned_post` answer **403**, not 401 | telling a known caller they are unauthenticated when they are merely not the owner | `api` |

## 5. Data cleaning at the boundary

Cheap, pure, no fixtures. Write these on the first evening — they are the rows
with the best ratio of confidence to effort.

| Invariant | Prevents | Level |
|---|---|---|
| `normalise_tags` strips, lower-cases, drops blanks, de-duplicates | `"Python"`, `"python "` and `"python"` becoming three tags | `unit` |
| `normalise_tags` **preserves the order typed** (`dict.fromkeys`, not `set`) | sorting, which throws away the author's emphasis — a decision nobody asked for | `unit` |
| `PostFormInput()` with no arguments is a valid blank form | the "new post" page needing a special case | `unit` |
| `PostFormInput.validated()` splits on commas, drops empties, delegates the rest to `PostForm` | the two surfaces accepting different things | `unit` |
| `post_to_input` re-joins tags with `", "` — the inverse of the above | an edit round-trip mangling tags. Property test: `validated(post_to_input(p)).tags == [t.name for t in p.tags]` | `unit` |
| `PostResponse.flatten_tags` accepts `Tag` rows *and* plain strings | breaking either the ORM path or the direct-construction path | `unit` |
| `Post.outline` returns `## ` headings, prefix stripped, in order; `[]` when none | the template's "show the summary instead" branch never firing | `unit` |
| `Post.reading_minutes` is `ceil(words/200)`, never below 1 | "0 min read" on a short post | `unit` |
| `User.image_path` is `/media/...` when set and `DEFAULT_AVATAR` when `None`, and has no setter | a second place the avatar lives, and two ways for them to disagree | `unit` |
| `PasswordResetToken.expired` labels a naive datetime from SQLite as UTC | SQLite has no tz-aware column, so comparing what comes back to an aware `now` raises instead of answering | `unit` |
| `Post.date_posted` default is a callable | every post stamped with the moment the process started | `unit` |
| password bounded at 8 and 128 | a multi-megabyte password making the server spend a long time hashing | `unit` |

## 6. Tokens and hashing

| Invariant | Prevents | Level |
|---|---|---|
| `verify_access_token` returns `None` for every bad case — wrong signature, expired, missing `exp`, missing `sub`, not a JWT | a missing expiry read as "never expires"; and telling a client which case it was, which only helps someone probing | `unit` |
| `create_access_token` always writes `exp` | a caller forgetting it | `unit` |
| a non-numeric `sub` is a 401, not a 500 | `int(None)` reaching the database layer | `api` |
| a validly signed token for a deleted account is a 401 | a ghost session | `db` |
| `hash_password` / `verify_password` round-trip; the hasher **raises** on a bcrypt hash rather than answering "no match" | anything writing `password_hash` outside `hash_password` failing at sign-in instead of at write time | `unit` |
| `hash_reset_token` is sha256 hex — deterministic, 64 chars | the column width, and lookup by hash working at all | `unit` |
| issuing a new reset token clears the previous ones | two live links to one account, the older being the likelier to have leaked | `db` |
| using a token clears every token for that user | replay | `db` |
| an expired token is deleted when it is found | rows accumulating, and a spent token being distinguishable from an absent one | `db` |
| `passwords.change` also clears reset tokens | a leaked link surviving the password change made *because* it leaked | `db` |
| `Unauthorized` carries `WWW-Authenticate: Bearer` | a client following the OAuth flow having nothing to answer | `unit` |
| `Settings` refuses to load without `SECRET_KEY` | a shipped default secret; and the failure arriving as a 500 on whichever request needs it first rather than at startup | `unit` |
| `FRONTEND_URL` actually lands on `frontend_url` | the field name drifting from the environment variable, so every reset link points at the default. *Already happened* (`fromtend_url`) | `unit` |

## 7. Images

| Invariant | Prevents | Level |
|---|---|---|
| the size ceiling is checked **before** the bytes are decoded | a decoder discovering that somebody sent a gigabyte | `api` |
| output is always JPEG, 300×300, RGB | a 12-megapixel portrait or a transparent PNG reaching the pages | `unit` |
| `RGBA`/`LA`/`P` is converted before saving | JPEG has no alpha channel and raises rather than flattening | `unit` |
| EXIF orientation is applied | phone portraits arriving sideways | `unit` |
| `fit()` crops to the aspect ratio, so a tall photo is not squashed | faces out of proportion | `unit` |
| the filename is a fresh uuid per upload | browsers and CDNs serving the previous picture from cache; and a name from the upload colliding or carrying path separators | `unit` |
| `delete` accepts `None` and a name already gone | callers having to check first | `unit` |
| the directory is created when absent | a fresh clone, where `media/` is not in the repository | `unit` |
| `UnidentifiedImageError` becomes a 400, not a 500 | a corrupt upload reading as a server fault | `api` |
| `remove_picture` with no picture is a 400, not a 404 | the account exists and the address is right; what is wrong is that the request asks for something already true | `api` |
| `storage.save` runs off the event loop | a CPU-bound resize blocking every other request | — |

## 8. The two surfaces answer in their own terms

| Invariant | Prevents | Level |
|---|---|---|
| under `/api/`, failures are JSON; everywhere else, an HTML page | a script getting markup, or a browser getting a JSON blob | `api` |
| the match is on the **unversioned** `/api/` root | `/api/v2` rendering HTML errors to clients that asked for JSON | `api` |
| the error page carries the **original** status, not 200 | a lie that caches, crawlers and monitoring all believe | `api` |
| validation errors: the field list for the API, one sentence for a page | the field-by-field breakdown belonging beside the inputs, which the form already does | `api` |
| `PostFormView.status_code` is 422 when it holds errors | a page full of complaints served as 200, telling a client, a cache and a crawler that the submission succeeded | `unit` |
| `PostFormView.editing` is derived, not passed | `mode="edit"` with `post=None` being constructible | `unit` |
| `form_errors` maps `min_length == 1` to "Required." and gives one message per field | Pydantic's raw wording reaching a reader | `unit` |
| `with_tag` is 404 only when `total == 0` | page four of a tag with thirty posts being "not found" when it is merely empty | `db` |
| pages are absent from `/openapi.json` | the contract test comparing unlike with unlike | `api` |
| every route name resolves, and page names do not collide with API names | `url_for("forgot_password")` silently returning `/api/…`. *Already happened* | `api` |
| `/posts/new` is matched before `/posts/{post_id}` | "new" parsed as a post id, answering 422 | `api` |
| `/static` gets `cache-control: no-cache`; `/media` does not | new HTML running against a cached script, which renders and then quietly does nothing. *Already happened*, and cost an hour | `api` |

## 9. The seams

Structural, and cheap because the type checker already agrees.

| Invariant | Prevents | Level |
|---|---|---|
| `DiskAvatars` satisfies `AvatarStorage`; `BackgroundMail` satisfies `ResetMailer` | a signature drifting on one side. `assert isinstance(...)` needs `@runtime_checkable`; a typed assignment in a test body is enough and costs nothing at runtime | `unit` |
| overriding `get_avatar_storage` moves every avatar off the disk | a test suite writing into `media/` and leaving a diff in the working tree | `api` |
| `find_related` prefers shared tags, ranks by `(shared count, recency)`, and falls back to newest with `shared=[]` | the heading logic on the post page, which distinguishes the two cases by `shared` alone | `db` |
| `find_related` never suggests the post being read | the obvious embarrassment | `db` |
| `get_or_create` returns rows in the order the names were given | the author's emphasis lost on the round trip | `db` |
| `get_or_create([])` is `[]` | a pointless query | `db` |
| `with_counts` makes an orphan tag invisible — the join is the filter | a tag with no posts on the topics page | `db` |

---

## Order to write them in

1. **Section 5, then the `unit` rows of 1 and 6.** No fixtures, no database,
   no event loop. This is a couple of evenings and it covers every boundary
   that is currently checked by nobody.
2. **The `session` and `client` fixtures.** They block everything else.
3. **The rows marked *already happened*.** Eight of them, spread across
   sections. Each is a bug that reached `master` once; a test that fails on it
   is worth more than any number of new ones.
4. **Sections 2 and 3.** The security family and the transaction ordering —
   the two places where a regression is silent *and* costly.
5. **The rest, opportunistically.** A row is a good candidate the moment you
   touch the code near it.

## What not to test

- **That SQLAlchemy and Pydantic work.** `unique=True` rejecting a duplicate is
  their test, not ours. What is ours is what the *application* does with the
  `IntegrityError`.
- **Route wiring already covered by Postman.** 375 assertions pass over the
  JSON surface; duplicating them in pytest buys nothing. Reach for `api`-level
  tests where the assertion is awkward in Postman — identical bodies, header
  presence, an overridden dependency.
- **The templates' markup.** The browser tests check that the right things are
  visible to the right person; asserting on class names makes a restyle a test
  failure.
- **Anything a `# *` marker does not defend.** If no comment explains why the
  code is the way it is, the behaviour is probably incidental, and a test would
  freeze an accident into a requirement.
