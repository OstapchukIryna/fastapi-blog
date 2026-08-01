# ADR-001: The HTML pages get their own router

**Status:** Accepted
**Date:** 31 Jul 2026

## Context

This application serves two interfaces from one codebase. `/api/*` answers
JSON to scripts. Everything else answers HTML to a person with a browser.

Only one of them had a home. The API lived in `routers/`, one module per
resource. The pages lived in `main.py`, which by then held the application
factory, the static mounts, the router wiring, the error handlers, sixteen
page handlers and two page helpers — 348 lines, and every new page made it
longer.

The split leaked in the other direction too. `PostFormView`, `post_to_input`
and `arrange` sat in `routers/posts.py`, the JSON router, which never called
any of them:

```
arrange        -> used only by main.py
find_related   -> used only by main.py
post_to_input  -> used only by main.py
PostFormView   -> used only by main.py
```

They were there because the post form was written when `main.py` was the only
other file, not because they are anything to do with the API. A reader opening
`routers/posts.py` to see what the API does met a dataclass about the state of
an HTML form.

## Decision

Add `routers/pages.py`, holding every HTML route and the state those routes
need. `main.py` becomes the application factory and nothing else.

## Options considered

### A. Leave it, split later when it hurts

| Dimension | Assessment |
|---|---|
| Effort now | None |
| Risk | None today, rising |
| Reversibility | n/a |

**For:** the file is navigable at 348 lines, and the project is one person's.
**Against:** the leak is the part that compounds. Each page added takes the
shortest path, which is another helper in the API router.

### B. `routers/pages.py` — one module for the HTML side

| Dimension | Assessment |
|---|---|
| Effort now | An afternoon, mechanical |
| Risk | Route names are what templates resolve; renaming any breaks a link |
| Reversibility | High — it is a move, not a rewrite |

**For:** matches how the project already organises the API. `main.py` becomes
readable in one screen. The API router stops carrying form state.
**Against:** `pages.py` is 400 lines, the largest module in the project.

### C. A `pages/` package, split by section

| Dimension | Assessment |
|---|---|
| Effort now | A day |
| Risk | Same, plus more import surface |
| Reversibility | High |

**For:** no module over ~120 lines.
**Against:** six modules for sixteen routes that share one set of helpers and
one template directory. The seams would be invented rather than found.

## Trade-off

B and C differ only in when the split happens. C buys smaller files at the
cost of deciding boundaries now, from a codebase where the pages have not yet
told us where they divide. B keeps one obvious boundary — HTML against JSON —
which the code already had and was failing to honour.

`pages.py` being the largest module is a fair objection, and the answer is
that it is large in the way a table of contents is large: sixteen short
handlers, each a template call.

## Consequences

**Easier.** `main.py` is 38 lines: lifespan, mounts, routers, error handlers.
A reader can see the shape of the application without scrolling. Adding a page
has an obvious home, and the API routers no longer offer one.

**Harder.** Two files to open when a change spans both interfaces — the post
form is the case, since it posts to a page route without a script and to the
API with one.

**To revisit.** If `pages.py` passes roughly 600 lines, or the post editor
grows a second form, split it by section as in option C. The seam will be
visible by then.

## What was done

- `routers/pages.py`: sixteen routes, plus `PostFormView`, `post_to_input`,
  `arrange`, `render_post_form` and `form_errors`.
- `routers/posts.py`: 385 → 308 lines, and now only about posts as data.
  `posts_query`, `find_related` and `set_pinned` stayed — they query and
  change posts, which is what that module is for.
- `main.py`: 348 → 38 lines.
- Route names unchanged, which is what kept every `url_for` in the templates
  working. Verified by opening all twelve pages and by 325 API assertions and
  3 browser tests.
