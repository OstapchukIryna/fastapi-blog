# The shape of this application

Four diagrams, each answering a question that costs time to re-derive by
reading: what may import what, which front door a request came in by, what
the data actually is, and what runs in the browser.

All of them were generated from the code rather than from memory — the import
graph by walking every module's AST, the API paths out of `/openapi.json`, the
page paths out of the decorators in `presentation/web/pages.py`. If a diagram
here is wrong, the code moved.

For how a request is *authenticated*, see [auth.md](auth.md). For why the
pages have their own router, [adr-001-pages-and-api.md](adr-001-pages-and-api.md).

---

## What may import what

Five layers, each a package under `src/blog/`, one module per thing inside it.
Every arrow points down, and the diagram shows the edges that carry
information — not the ones every module has. Nearly everything above
`infrastructure` also imports `models` and `database` for the ORM classes and
the `DbSession` alias, and drawing that a dozen more times would have said only
that the layers exist.

```mermaid
graph TD
    main["main.py · 44 lines<br/><i>lifespan, mounts, routers</i>"]

    subgraph L4["presentation · what HTTP and Jinja look like"]
        pages["web/pages.py · 16 routes<br/>web/forms.py · состояние формы<br/>web/templating.py<br/><b>HTML</b>"]
        api["api/posts.py · api/users.py<br/>api/tags.py<br/><b>JSON</b> · 10 paths"]
        errors["errors.py"]
    end

    subgraph L3["services · что приложение умеет и на каких условиях"]
        s_posts["posts.py<br/><i>запросы, PostDep, OwnedPost</i>"]
        s_users["users.py<br/><i>UserDep, OwnAccount</i>"]
        s_tags["tags.py"]
        s_auth["auth.py<br/><i>CurrentUser</i>"]
    end

    subgraph L2["schemas · формы данных на границе"]
        schemas["post.py · user.py · tag.py"]
    end

    subgraph L1["infrastructure · где данные лежат"]
        models["models/post.py<br/>models/user.py · models/tag.py"]
        database["database.py<br/><i>engine, DbSession</i>"]
        images["images.py"]
    end

    subgraph L0["core · не импортирует ничего нашего"]
        config["config.py<br/><i>settings, BASE_DIR</i>"]
        security["security.py<br/><i>tokens, hashing</i>"]
    end

    main --> pages
    main --> api
    main --> errors

    errors --> pages
    api --> s_posts
    api --> s_users
    api --> s_tags
    api --> s_auth
    pages --> s_posts
    pages --> s_users
    pages --> s_tags
    pages --> s_auth

    s_posts --> s_tags
    s_posts --> s_auth
    s_users --> s_auth

    s_posts --> schemas
    s_users --> schemas
    s_users --> images
    s_auth --> security

    schemas --> models
    models --> database
    security --> config
    database --> config
```

**The rule this records:** arrows only ever point downwards, and the one place
it is easy to break is `presentation`. `web/` does not import `api/` — both ask
`services/` instead, which is why «пост не найден» is one place in the code
rather than two that drifted apart. Before the split it was not like that:
`pages` imported the JSON routers for `posts_query` and the dependencies, and
every page inherited whatever the API happened to need.

A module below importing a router is the mistake that already happened once —
`schemas.py` imported the tags router for a tag-cleaning helper, and since that
router imported `schemas` back by way of the posts one, the application stopped
importing at all. The helper was pure data cleaning and belongs where it now
sits, in `schemas/tag.py`.

**Two arrows inside `services` worth explaining.** `posts.py` imports `tags.py`
because storing a post means creating the tags it names; `users.py` and
`posts.py` both import `auth.py` because ownership is a question about the
current user. Nothing points back: `tags.py` returns tags, never posts, and
what returns posts *by* tag lives in `posts.py`. Otherwise the two would
import each other.

`seed.py` is off the diagram. It imports `core.security`, `infrastructure` and
`services.tags` and is imported by nothing; it is a script, not part of the
running application.

---

## Two front doors

```mermaid
graph LR
    person([a person]) --> pages_r
    script([a script,<br/>Postman, fetch]) --> api_r

    subgraph pages_r["presentation/web/pages.py — 16 routes, include_in_schema=False"]
        direction TB
        p1["/ · /posts · /posts/{id}<br/>/tags · /tags/{tag}<br/>/users/{id}/posts · /about"]
        p2["/posts/new · /posts/{id}/edit<br/>/posts/{id}/pin · /posts/{id}/delete"]
        p3["/login · /register · /profile"]
    end

    subgraph api_r["presentation/api/*.py — 10 paths, the documented surface"]
        a1["/api/posts · /api/posts/{id}"]
        a2["/api/users · /api/users/{id}<br/>/api/users/{id}/picture<br/>/api/users/{id}/posts"]
        a3["/api/users/token · /api/users/me"]
        a4["/api/tags · /api/tags/{tag}/posts"]
    end

    pages_r --> jinja[Jinja templates]
    api_r --> pyd[Pydantic response models]
    p3 -. "the page is a shell;<br/>its script calls the API" .-> api_r
```

The dotted arrow is the thing to hold on to. **Sign-in, registration and the
profile render as empty shells and fill themselves from the API**, because the
token lives in `localStorage` and Jinja cannot see it. Every other page is
rendered whole by the server.

That is also why the pages are `include_in_schema=False`: `/openapi.json`
describes the ten API paths and nothing else, so the contract test in the
Postman collection compares like with like.

---

## The data

```mermaid
erDiagram
    USER ||--o{ POST : writes
    POST }o--o{ TAG : "post_tags"

    USER {
        int id PK
        string username UK "50, unique"
        string email UK "120, unique, stored lower-case"
        string password_hash "argon2"
        string image_file "nullable — null means the shared default"
    }

    POST {
        int id PK
        string title "100"
        string summary "250"
        text content "markdown"
        bool is_pinned "at most one true, enforced in set_pinned"
        int user_id FK "cascade on delete"
        datetime date_posted "indexed, newest first"
    }

    TAG {
        int id PK
        string name UK "30, indexed, lower-case"
    }
```

Three things the columns do not say:

- **`image_file` null is meaningful.** It means "no photo of their own", and
  `User.image_path` turns it into `/static/profile_pics/default.jpg`. Deleting
  a picture sets it back to null and removes the file.
- **`is_pinned` is a single-winner flag** with no constraint behind it.
  `set_pinned` in `services/posts.py` clears the others in the same
  transaction; nothing in the schema would stop two rows being true if
  something else wrote them.
- **Deleting a user cascades to their posts** and to their uploaded file.
  Tags are left behind even when nothing references them any more — they
  become invisible in `/api/tags`, which counts through posts, but they do
  accumulate.

---

## What runs in the browser

```mermaid
graph TD
    subgraph shared["static/js — no build step, plain ES modules"]
        auth_js["auth.js<br/>the token: read, save, clear,<br/>who it belongs to"]
        utils_js["utils.js<br/>sendJSON · wireForm<br/>the two result windows"]
    end

    layout["layout.html<br/>every page"] --> auth_js
    login["login.html"] --> auth_js
    login --> utils_js
    register["register.html"] --> utils_js
    post_form["post_form.html"] --> auth_js
    post_form --> utils_js
    profile["profile.html"] --> auth_js
    profile --> utils_js

    auth_js -. "no import between them" .- utils_js
```

`auth.js` and `utils.js` **do not know about each other**, and that is
deliberate: one is about identity, the other about talking to an API and
reporting the result. A page that needs both composes them; a page that needs
one carries one. `register.html` needs no token, so it never loads `auth.js`.

`layout.html` loads only `auth.js`, because the one thing every page decides
is which of *Sign in* / *Sign out* to show and whether to reveal controls
marked `data-author-only`.

---

## What is covered by what

| Layer | Tool | Count | What it can see |
|---|---|---|---|
| API contract | Postman / Newman | 81 requests, 325 assertions | Every documented path, every refusal, ownership |
| Live pages | Playwright | 3 journeys | What the scripts do with real answers |
| Pure JS functions | — | none yet | `currentUserId` parsing, error wording |
| Routes and templates | — | none yet | That a page renders at all |

```bash
./scripts/api-tests.sh   # throwaway database, throwaway server, no trace left
uv run pytest            # the three browser journeys
```

The two empty rows are the cheap ones, and they are empty because the
expensive layers were written first — the API tests because the API is the
contract, and the browser tests because a dialog that leaves the page
scroll-locked cannot be seen from anywhere else. `node --test` needs no
dependency at all for the first of them.

Nothing runs automatically: there is no CI workflow in the repository. Both
commands are things to run by hand before pushing.
