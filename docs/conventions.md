# Conventions

How this codebase is written, and what the markings in it mean.

## Comments explain why

The code already says what happens. A comment earns its place by saying
something the code cannot: the reason for a choice, the trap avoided, the
alternative that was tried and failed.

```python
# no: repeats the line below it
# increment the counter
count += 1

# yes: says what the reader could not have known
# ! JPEG has no alpha channel; saving a transparent image as one
# ! raises rather than flattening it.
if image.mode in ("RGBA", "LA", "P"):
    image = image.convert("RGB")
```

## Better Comments markers

Comments are prefixed so an editor can colour intent apart from prose.
The markers work in Python, JavaScript and Jinja alike.

| Marker | Means | Use it for |
|---|---|---|
| `# *` | worth noticing | the reason behind a decision |
| `# !` | a trap | something that fails silently, or fails far from its cause |
| `# ?` | an open question | a choice not yet settled |
| `# TODO:` | known work | debt, with its blocker named |

In JavaScript the same markers follow `//`, and inside a JSDoc block they
follow the leading `*`. In Jinja they go inside `{# … #}`.

Install [Better Comments][bc] to see them coloured; without it they are
ordinary comments and nothing is lost.

[bc]: https://marketplace.visualstudio.com/items?itemName=aaron-bond.better-comments

## Docstrings

Google style, which is what [autoDocstring][ad] generates by default and
what the `mkdocstrings` handler on this site is configured to read. Set
the extension's format to `google` and a stub arrives in the right shape.

[ad]: https://marketplace.visualstudio.com/items?itemName=njpwerner.autodocstring

```python
def with_counts(db: AsyncSession, page: Pagination) -> tuple[Sequence[Row], int]:
    """List tags with how many posts use each, most used first.

    Ties are broken by name so the order is fully determined. Without
    that, two tags with the same count could swap places between
    requests, and one would appear on two consecutive pages.

    Args:
        db (AsyncSession): session to query through.
        page (Pagination): which slice to return.

    Returns:
        tuple[Sequence[Row], int]: the rows, and how many exist in total.
    """
```

Rules that follow from that:

- **Every module, class, function and property has one.** A one-line
  summary is enough when there is genuinely nothing else to say.
- **The first line is a sentence in the imperative or the indicative**,
  not a repetition of the name. `"""Store a new post."""`, not
  `"""create_post."""`
- **`Attributes:` on a class** carries the same weight as `Args:` on a
  function — especially where a field is nullable, derived or read-only,
  because that is where a reader's assumption goes wrong.
- **`Raises:` whenever the function refuses.** A caller cannot handle a
  refusal it does not know exists.

## Types

Every parameter and every return is annotated, including `-> None`.

One rule is specific to FastAPI and worth stating on its own:

!!! danger "Dependency aliases must exist at runtime"

    `DbSession = Annotated[AsyncSession, Depends(get_db)]` is a value,
    not just a type. FastAPI reads annotations at runtime to resolve
    dependencies, so moving the import under `TYPE_CHECKING` does not
    fail loudly — the parameter silently becomes a query parameter and
    the endpoint starts answering 422 with nothing in the log.

    This is why `TC001`, `TC002` and `TC003` are disabled for the whole
    project in `pyproject.toml`.

## Layering

Imports point down or sideways, never up:

```
presentation  →  services  →  schemas  →  infrastructure  →  core
```

A sideways import — between two modules in the same layer — is allowed
but must be declared, with its reason, in `ALLOWED_SIDEWAYS` in
`tests/test_import_graph.py`. Both import cycles this project has had
began as a sideways import added without thinking.

The question to ask before adding one:

> If neither of these two entities existed, would this thing still make
> sense?

If yes, it is shared vocabulary and belongs a layer down. If no, it is a
real dependency and belongs where it is, with a line explaining why.
