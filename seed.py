from pathlib import Path

CONTENT_DIR = Path(__file__).parent / "content"


def load(slug: str) -> str:
    return (CONTENT_DIR / f"{slug}.md").read_text(encoding="utf-8")


posts: list[dict] = [
    {
        "id": 5,
        "author": "called_mad",
        "title": "I replaced pip, black and mypy in one afternoon",
        "date_posted": "26 Jul 2026",
        "tags": ["tooling", "python"],
        "summary": (
            "uv, ruff and pyrefly in place of four older tools — what the "
            "switch actually changed, and where the old ones still matter."
        ),
        "content": load("modern-python-tooling"),
    },
    {
        "id": 4,
        "author": "called_mad",
        "title": "The Pydantic validator mistake that returns None",
        "date_posted": "22 Jul 2026",
        "tags": ["pydantic", "python"],
        "summary": (
            "A validator that forgets to return does not fail loudly. It "
            "quietly sets the field to None."
        ),
        "content": load("pydantic-validators"),
    },
    {
        "id": 3,
        "author": "called_mad",
        "title": "Threads didn't make it faster. Processes did.",
        "date_posted": "18 Jul 2026",
        "tags": ["async", "python"],
        "summary": (
            "Twelve images, two halves of one script, and two opposite "
            "results from the same tool. The GIL explains both."
        ),
        "content": load("threads-vs-processes"),
        "pinned": True,
    },
    {
        "id": 2,
        "author": "called_mad",
        "title": "Why you can't filter a window function in WHERE",
        "date_posted": "12 Jul 2026",
        "tags": ["sql"],
        "summary": (
            "The column exists four lines above the error. The problem is "
            "not where it is, but when it is evaluated."
        ),
        "content": load("window-functions-cte"),
    },
    {
        "id": 1,
        "author": "called_mad",
        "title": "What actually happens when a dict resizes",
        "date_posted": "5 Jul 2026",
        "tags": ["python", "internals"],
        "summary": (
            "Two-thirds full, powers of two, and one unlucky insert that "
            "pays for rehashing the entire table."
        ),
        "content": load("dict-resize"),
    },
]
