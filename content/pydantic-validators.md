There is one mistake in Pydantic validators that produces no error, no warning,
and a field that is silently `None`.

```python
@field_validator("username")
@classmethod
def normalise(cls, v: str) -> str:
    v.lower()  # результат никуда не идёт
```

The field is now `None`. Not the original value, not the lowered one — nothing.
The validator returned `None` implicitly, and Pydantic took it at its word.

## The rule

**Always return the value, even when you changed nothing.**

```python
@field_validator("username")
@classmethod
def normalise(cls, v: str) -> str:
    if not v.replace("_", "").isalnum():
        raise ValueError("username must be alphanumeric")
    return v.lower()
```

## Which exception

Raise `ValueError`. Pydantic catches it and folds it into a `ValidationError`
with the field name and location attached. `AssertionError` works the same way.

`TypeError` does **not**. In v2 it propagates untouched, so a validator that
raises it will produce a raw traceback instead of a clean 422 response.

## Do not mutate before raising

If a validator transforms the value and then raises, the transformation is
discarded — the `return` never happens. It is not an error, it is just dead
code that reads as if it did something.