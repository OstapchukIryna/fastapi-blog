"""See the SQL a piece of code actually emits, and how long each statement took.

Two ways to look at queries, and they answer different questions.
`create_async_engine(..., echo=True)` prints everything to the log, which is
what you want while clicking through the application. This module collects
statements into a list instead, which is what you want when the question is
*how many* — whether eager loading is in place, whether a change added a query
per row, whether the count and the page are one round trip or two.

Run it to see the query profile of the read paths:

    uv run python scripts/sqlwatch.py

The `watching` context manager is the reusable part. It works in a test as it
does here, which is what makes "this endpoint issues a constant number of
queries" an assertion rather than a hope:

    with watching(engine) as queries:
        await posts.list_all(session, Pagination())

    assert len(queries) == 3  # count, posts, tags
"""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from blog.infrastructure.database import AsyncSessionLocal, engine
from blog.schemas.pagination import Pagination
from blog.services import posts, tags


@dataclass(slots=True, frozen=True)
class Query:
    """One statement as the driver received it.

    Attributes:
        statement (str): the SQL, after SQLAlchemy has compiled it. Bind
            values are still placeholders — that is what the driver sees,
            and it is why the same query text can be reused from a cache.
        parameters (Any): the bind values. A tuple for one execution, a
            list of tuples for an executemany.
        milliseconds (float): wall time between the two events. Includes
            driver overhead, so it is useful for comparing statements
            against each other rather than as an absolute number.
    """

    statement: str
    parameters: Any
    milliseconds: float

    @property
    def first_line(self) -> str:
        """The statement collapsed to one line, for a summary listing.

        Returns:
            str: whitespace squeezed out, cut at 100 characters.
        """
        flat = " ".join(self.statement.split())
        return flat if len(flat) <= 100 else f"{flat[:97]}..."


@contextmanager
def watching(target: AsyncEngine) -> Iterator[list[Query]]:
    """Collect every statement executed while the block runs.

    Args:
        target (AsyncEngine): the engine to listen on.

    Yields:
        list[Query]: filled as statements execute. Read it after the block,
            or during — it is the same list object throughout.
    """
    collected: list[Query] = []

    # ! Events are registered on `engine.sync_engine`, not on the async
    # ! engine. An AsyncEngine is a facade over a synchronous one, and the
    # ! event system lives underneath it — `event.listen(engine, ...)` on
    # ! the async object raises InvalidRequestError, which is a good error
    # ! to get, but only if you know what it is telling you.
    underlying = target.sync_engine

    def before(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        """Stamp the start time on the connection.

        On the connection rather than in a closure variable: statements can
        overlap across connections, and a single timer would then measure
        the gap between two unrelated queries.
        """
        conn.info["sqlwatch_started"] = perf_counter()

    def after(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        """Record the statement together with its elapsed time."""
        started = conn.info.pop("sqlwatch_started", None)
        elapsed = (perf_counter() - started) * 1000 if started else 0.0
        collected.append(Query(statement=statement, parameters=parameters, milliseconds=elapsed))

    event.listen(underlying, "before_cursor_execute", before)
    event.listen(underlying, "after_cursor_execute", after)
    try:
        yield collected
    finally:
        # * Removed in a finally, so a failing assertion inside the block
        # * does not leave a listener attached to a process-wide engine and
        # * quietly pollute the next measurement.
        event.remove(underlying, "before_cursor_execute", before)
        event.remove(underlying, "after_cursor_execute", after)


def report(label: str, queries: list[Query], *, full: bool = False) -> None:
    """Print what was collected.

    Args:
        label (str): what was being measured.
        queries (list[Query]): the statements, in execution order.
        full (bool): print each statement in full, with its bind values,
            rather than one squeezed line each.
    """
    total = sum(query.milliseconds for query in queries)
    print(
        f"\n{label}\n  {len(queries)} quer{'y' if len(queries) == 1 else 'ies'}, "
        f"{total:.1f} ms total"
    )
    for number, query in enumerate(queries, 1):
        if full:
            print(f"\n  [{number}] {query.milliseconds:5.1f} ms")
            print("      " + query.statement.strip().replace("\n", "\n      "))
            print(f"      -- params: {query.parameters}")
        else:
            print(f"  [{number}] {query.milliseconds:5.1f} ms  {query.first_line}")


async def main() -> None:
    """Profile the read paths that serve a page."""
    page = Pagination()

    async with AsyncSessionLocal() as session:
        with watching(engine) as queries:
            await posts.list_all(session, page)
        report("posts.list_all — the front page", queries, full=True)

        with watching(engine) as queries:
            await tags.with_counts(session, page)
        report("tags.with_counts — the topics page", queries)

        found, _ = await posts.list_all(session, page)
        if found:
            with watching(engine) as queries:
                await posts.find_related(session, found[0])
            report("posts.find_related — under one post", queries)

        # * The number that matters is that it does not move with the page
        # * size. Three queries for ten posts and three for a hundred is
        # * what "no N+1" means; if this ever prints a fourth, something
        # * started loading per row.
        for size in (1, 10, 100):
            with watching(engine) as queries:
                await posts.list_all(session, Pagination(limit=size))
            print(f"\nlist_all(limit={size:>3}) -> {len(queries)} queries")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
