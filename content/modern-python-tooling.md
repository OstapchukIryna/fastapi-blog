I replaced four tools with three in an afternoon and have not looked back.

| was | now |
| --- | --- |
| pip + venv + pip-tools | `uv` |
| black + flake8 + isort | `ruff` |
| mypy | `pyrefly` |

All three are written in Rust, and the difference is not marginal. Installing a
dependency set that took forty seconds now takes under two.

## uv

It manages the environment, the lockfile and the Python version itself. The
part that changed my habits most is `uv run` — it resolves the project's
environment on every invocation, so there is nothing to activate and nothing to
forget to activate.

## ruff

Linter and formatter in one binary. Worth knowing that the rule sets are opt-in:
`PTH` catches `os.path` usage and suggests `pathlib`, `ASYNC` catches blocking
calls inside async functions. Neither is on by default, and both catch mistakes
I had actually made.

## pyrefly

Type checking, chosen over the faster `ty` because `ty` is still pre-1.0 and
covers noticeably less of the typing specification.

My rule: run several type checkers over the tests, one over the source. Checkers
agree about behaviour at the boundary and disagree about implementation details,
so two of them on source code means satisfying two contradictory opinions about
the same line.

---

The caveat: `pip`, `black` and `mypy` are what you will find in an existing
codebase. Modern tooling for personal work, familiarity with the standard set
for everything else.