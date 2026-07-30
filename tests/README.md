# Browser tests

Three journeys, driven through a real Chromium by Playwright.

```bash
uv run pytest
```

First run on a new machine needs the browser itself, once:

```bash
uv run playwright install chromium
```

The fixtures seed a temporary database, serve it on a port the operating
system picks, and stop it afterwards. `blog.db` is never touched — and
the port is asked for rather than chosen, because a stray server from
another session once answered on the usual one and a test suite would
have passed against the wrong application entirely.

## Why only three

This is the slowest and most fragile layer, and it is the last place to
put a check that something cheaper could make. The split:

| Question | Answered by |
|---|---|
| Does the API keep its promises? | `postman/`, 289 assertions |
| Do the pure JS functions parse what they are given? | not yet written |
| Do the routes render? | not yet written |
| Does the page do the right thing with a real answer? | here |

So these three exist for behaviour that only appears when a browser runs
the scripts: what happens to a token, which menu entry shows, which
control is offered to whom.

1. **register → sign in → publish.** Nothing is set up in advance; the
   account is made through the form the way a person makes one, and the
   post is written with the token that signing in produced. Every link
   in the chain is load-bearing.
2. **An expired token is noticed on the profile.** Tokens last thirty
   minutes, so this is the ordinary end of a session. Nothing tells the
   browser the token died — the page has to ask, be refused, say so, and
   throw the token away.
3. **Edit is offered to the author only.** Three readers, one post: a
   stranger with no account, somebody signed in who did not write it,
   and the author. The middle one is the case worth having.

## Each of them was checked by breaking something

A green test that asserts nothing is worse than no test, so each was made
to fail on purpose before being kept:

| Break | Test that caught it |
|---|---|
| post form stops sending the token | register → sign in → publish |
| profile stops discarding a dead token | expired token |
| the layout reveals every author-only control | Edit for the author only |

In each case exactly one test failed, which is the other half of the
check: a test that fails for everything localises nothing.

## Notes

The signing secret is fixed in `conftest.py` and used nowhere else. The
expired-token test mints its own token, which is impossible without
knowing it — and an expired token cannot be obtained any other way
except by waiting half an hour.

Accounts are named after the test that asked for them, so a failure
leaves rows you can read rather than a timestamp.
