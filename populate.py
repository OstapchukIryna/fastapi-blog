"""Наполнение базы демонстрационными данными: шесть авторов, 45 постов.

    uv run python populate.py

ОСТОРОЖНО: скрипт разрушающий. Он сносит всех пользователей, все посты,
все теги и все загруженные аватары — и только потом наполняет заново.
Иначе смысла нет: пагинацию видно только на точном количестве записей, а
идемпотентный догон дал бы каждый раз разное число страниц.

Постов 45, а не круглые 40: при десяти на страницу последняя выходит
неполной, и это единственный случай, который ловит ошибку на единицу
в ссылке «последняя».

Чем отличается от seed.py, и почему это два скрипта, а не один:

    seed.py       пять настоящих постов, тексты из content/*.md,
                  идемпотентен, пишет напрямую через ORM.
                  Его гоняют tests/conftest.py и scripts/api-tests.sh,
                  поэтому он обязан быть быстрым и предсказуемым.

    populate.py   объём. Ходит через настоящий API поверх ASGITransport —
                  те же роуты, что и у браузера, включая регистрацию,
                  выдачу токена и загрузку картинки. Медленнее (шесть
                  хешей argon2 и пять раз Pillow), зато заодно проверяет,
                  что публичный контракт цел.

Тексты постов свои. Аватары рисуются на месте, а не лежат в репозитории:
это демонстрационные данные, а не исходник.
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import NotRequired, TypedDict

import httpx
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import delete, select, update

from blog.infrastructure import models
from blog.infrastructure.database import AsyncSessionLocal, Base, engine
from blog.infrastructure.images import PROFILE_PICS_DIR
from blog.main import app


class UserSeed(TypedDict):
    username: str
    email: str
    password: str
    colour: NotRequired[tuple[int, int, int]]


class PostSeed(TypedDict):
    title: str
    summary: str
    content: str
    tags: list[str]
    author: NotRequired[int]  # индекс в USERS; по умолчанию 0
    pinned: NotRequired[bool]


# Пароли годятся ровно для локальной базы. Почта на example.com —
# домен зарезервирован RFC 2606 и ни к кому не приедет.
USERS: list[UserSeed] = [
    {
        "username": "called_mad",
        "email": "called_mad@example.com",
        "password": "TestPassword123",
        "colour": (255, 183, 3),
    },
    {
        "username": "off_by_one",
        "email": "off_by_one@example.com",
        "password": "TestPassword123",
        "colour": (166, 226, 46),
    },
    {
        "username": "tail_minus_f",
        "email": "tail_minus_f@example.com",
        "password": "TestPassword123",
        "colour": (102, 217, 239),
    },
    {
        "username": "nine_lives",
        "email": "nine_lives@example.com",
        "password": "TestPassword123",
        "colour": (249, 38, 114),
    },
    {
        "username": "grep_and_hope",
        "email": "grep_and_hope@example.com",
        "password": "TestPassword123",
        "colour": (174, 129, 255),
    },
    {
        # Без картинки намеренно: единственный способ увидеть на живой
        # странице, что image_path отдаёт общий default.jpg.
        "username": "plain_defaults",
        "email": "plain_defaults@example.com",
        "password": "TestPassword123",
    },
]

# Сверху новые, снизу старые — даты проставляются по индексу.
# Тексты короткие: это данные для листания, а не для чтения. Настоящие
# посты лежат в content/*.md и приезжают через seed.py.
POSTS: list[PostSeed] = [
    {
        "title": "The N+1 you can't see in the logs",
        "summary": (
            "One page, forty-one queries, and nothing in the output that "
            "looks wrong. The template was doing the asking."
        ),
        "content": (
            "The route ran one SELECT. The page then touched `post.tags` "
            "inside a loop, and SQLAlchemy went back to the database once "
            "per post, lazily, exactly as it promised to.\n\n"
            "`selectinload` fixes it in one line. The reason it is not "
            "speculative optimisation is that the cost scales with content: "
            "five posts on the page today, forty after this script runs."
        ),
        "tags": ["sqlalchemy", "python"],
    },
    {
        "title": "A 422 with nothing in the log is not FastAPI being rude",
        "summary": (
            "The dependency alias stopped existing at runtime, so the "
            "session became a query parameter. Nobody raised anything."
        ),
        "content": (
            "`DbSession = Annotated[AsyncSession, Depends(get_db)]` moved "
            "under `TYPE_CHECKING` because a linter said the import was "
            "only used in annotations. FastAPI reads annotations at "
            "runtime to resolve dependencies.\n\n"
            "So the alias was gone, `db` became an ordinary query "
            "parameter, and `GET /api/tags` started answering *Field "
            "required, loc: [query, db]*. A silent change of contract is "
            "worse than a crash."
        ),
        "tags": ["fastapi", "python", "tooling"],
    },
    {
        "title": "PUT that quietly became PATCH",
        "summary": (
            "One `exclude_unset=True` in the wrong handler, and two "
            "endpoints started doing the same thing."
        ),
        "content": (
            "PUT is a full replacement: a field the client omits is not "
            "*unchanged*, it becomes whatever the model defaults it to. "
            "Dump without `exclude_unset` and that stays true.\n\n"
            "With it, PUT leaves omitted fields alone — which is PATCH. "
            "Both endpoints pass their tests, and the difference between "
            "them is now a lie in the documentation."
        ),
        "tags": ["http", "fastapi", "pydantic"],
    },
    {
        "title": "The ownership check belongs in the dependency",
        "summary": (
            "If the first line of five routes is the same `if`, it was "
            "never a step. It was a precondition."
        ),
        "content": (
            "`post: OwnedPost` in a signature says two things at once — "
            "the post exists, and it is yours to change. The 404 and the "
            "403 both happen before the body runs.\n\n"
            "What is left in the route is the thing the route is actually "
            "for. That is the whole trick, and it is the difference "
            "between code that works and code that reads as its own "
            "summary."
        ),
        "tags": ["fastapi", "python"],
        "pinned": True,
    },
    {
        "title": "argon2 doesn't return False on a bcrypt hash. It raises.",
        "summary": (
            "The seeded author could not log in at all, and it was a 500 "
            "rather than a 401. Two hashers, one column."
        ),
        "content": (
            "The seeding script hashed with bcrypt; the application "
            "verified with pwdlib built for Argon2 only. It does not "
            "recognise the prefix, so it does not answer *no* — it "
            "throws.\n\n"
            "Fix: the script calls the same `hash_password` that "
            "registration calls. One function, one format, and the test "
            "account behaves like a real one."
        ),
        "tags": ["security", "python"],
        "author": 1,
    },
    {
        "title": "OFFSET is fine until it isn't",
        "summary": (
            "LIMIT 10 OFFSET 4000 reads four thousand rows to throw them "
            "away. On page one you will never notice."
        ),
        "content": (
            "Offset pagination is simple, bookmarkable and correct, and "
            "the database still walks every skipped row. For a blog with "
            "forty-four posts that is free.\n\n"
            "Cursor pagination — *give me what comes after this id* — "
            "stays flat, and loses the ability to jump to page seven. "
            "Pick the one whose weakness you can live with."
        ),
        "tags": ["sql", "http"],
    },
    {
        "title": "Your ORDER BY has to be total",
        "summary": (
            "Two rows with the same timestamp, and a post shows up on "
            "page one and page two while another never appears."
        ),
        "content": (
            "`ORDER BY date_posted DESC` is not a total order if two "
            "posts share a second — and a batch insert makes that likely. "
            "The database is free to return ties in any order, and it "
            "will pick a different one per query.\n\n"
            "Add the primary key as the last sort key. It costs nothing "
            "and makes the pages disjoint."
        ),
        "tags": ["sql", "sqlalchemy"],
        "author": 2,
    },
    {
        "title": "LIMIT and joinedload are a trap together",
        "summary": (
            "Ten rows of a join are not ten posts. The page comes back "
            "with four, and the query looks perfectly sensible."
        ),
        "content": (
            "`joinedload` on a many-to-one is safe: one row per post. On "
            "a collection it multiplies rows, and `LIMIT 10` then slices "
            "join output, not entities.\n\n"
            "`selectinload` issues a second query and keeps the count "
            "honest. Swapping one for the other looks like a harmless "
            "optimisation, which is exactly why it needs a comment."
        ),
        "tags": ["sqlalchemy", "sql"],
    },
    {
        "title": "COUNT(*) does not need your ORDER BY",
        "summary": (
            "Sorting a subquery you are about to count is work nobody "
            "asked for, and some databases refuse outright."
        ),
        "content": (
            "Building the total from the same `Select` as the page is the "
            "right instinct — it guarantees the filters match. Strip the "
            "ordering first with `order_by(None)`.\n\n"
            "Also strip the eager loading. Counting rows does not need "
            "the author of each one."
        ),
        "tags": ["sql", "sqlalchemy"],
        "author": 5,
    },
    {
        "title": "A pinned post and page two disagree",
        "summary": (
            "The front page pulls the pinned post out of the current "
            "slice. On page two there is no pinned post in the slice."
        ),
        "content": (
            "So the layout picks whatever came first instead, and the "
            "reader gets a random post in the hero slot. Worse: if the "
            "pinned post is not excluded from the ordinary list, it "
            "appears twice — once at the top, once wherever its date "
            "puts it.\n\n"
            "Decide it once: pinned belongs to page one, and comes out of "
            "the rest of the query entirely."
        ),
        "tags": ["fastapi", "sql"],
        "author": 3,
    },
    {
        "title": "Two front doors, one set of rules",
        "summary": (
            "The HTML form and POST /api/posts used to be two code paths "
            "that agreed by coincidence."
        ),
        "content": (
            "They validated the same fields with different models and "
            "refused with different words. Nothing enforced that they "
            "stay in step, and they did not.\n\n"
            "Now both call the same service function. *Post not found* is "
            "one place in the code, and the page and the JSON say it the "
            "same way because it is literally the same string."
        ),
        "tags": ["fastapi", "python"],
    },
    {
        "title": "Return the exception, raise it where you decided",
        "summary": (
            "A helper that raises hides the decision. A helper that "
            "returns an HTTPException keeps `raise` at the branch."
        ),
        "content": (
            '`raise unauthorized("Invalid or expired token")` reads as '
            "one sentence, and the control flow is visible at the site "
            "that refused.\n\n"
            "The header matters too: without `WWW-Authenticate` a 401 is "
            "just a status, not a challenge, and the OAuth flow has "
            "nothing to answer."
        ),
        "tags": ["fastapi", "security", "http"],
        "author": 4,
    },
    {
        "title": "Never say which half of the credentials was wrong",
        "summary": (
            "*Unknown email* and *wrong password* answer a question the "
            "caller had no right to ask."
        ),
        "content": (
            "Between them they confirm whether an address is registered "
            "here, to anybody who types one in. The same applies to "
            "registration: *username or email already taken*, without "
            "saying which.\n\n"
            "It costs one sentence of helpfulness and buys back the fact "
            "that your user list is not enumerable."
        ),
        "tags": ["security", "http"],
    },
    {
        "title": "The unique index will catch the race you checked for",
        "summary": (
            "Two requests both pass the SELECT, both insert, and one gets "
            "a 500 unless you are ready for it."
        ),
        "content": (
            "Checking before the insert is worth doing — it gives a clean "
            "400 in the common case. It just is not a guarantee, because "
            "the gap between the check and the commit is real.\n\n"
            "Catch `IntegrityError`, roll back, and raise the same 400. "
            "The loser of the race gets the same answer as somebody who "
            "was simply late."
        ),
        "tags": ["sql", "sqlalchemy", "python"],
        "author": 1,
    },
    {
        "title": "int(None) is a refusal you can catch",
        "summary": (
            "A rejected token gives None, a junk `sub` gives a string. "
            "One conversion turns both into the same 401."
        ),
        "content": (
            "`int(verify_access_token(token))` raises `TypeError` for the "
            "first and `ValueError` for the second, and the handler says "
            "*invalid or expired token* to both.\n\n"
            "The type checker hates it and it is right to: the signature "
            "says `str | None`. That is a note worth leaving in the code "
            "rather than an error worth silencing."
        ),
        "tags": ["python", "security"],
    },
    {
        "title": "Deleting twice should 404, not 204",
        "summary": (
            "DELETE is idempotent in its effect. That is not the same as "
            "pretending the second call found something."
        ),
        "content": (
            "The post is gone either way, which is what idempotent means. "
            "But answering 204 to a request for an id that does not exist "
            "is a claim about the world that is false.\n\n"
            "404 on the second call is the honest report, and it is what "
            "lets a client tell *I deleted it* from *somebody else "
            "already had*."
        ),
        "tags": ["http", "fastapi"],
        "author": 2,
    },
    {
        "title": "Tags survive the posts that used them",
        "summary": (
            "Deleting a post drops its rows in the link table. The tag "
            "row itself stays, invisible and accumulating."
        ),
        "content": (
            "`/api/tags` counts through posts, so an orphaned tag reports "
            "zero and never appears. It is still there, still holding the "
            "unique index on its name.\n\n"
            "Harmless at this size, and worth writing down before it is "
            "not: the cleanup either runs somewhere, or the table grows "
            "forever."
        ),
        "tags": ["sql", "sqlalchemy"],
    },
    {
        "title": "SQLite ignores your foreign keys by default",
        "summary": (
            "ON DELETE CASCADE is in the schema, the pragma is off, and "
            "the orphan rows stay exactly where they were."
        ),
        "content": (
            "SQLite enforces foreign keys only when `PRAGMA foreign_keys "
            "= ON` is set, per connection. SQLAlchemy does not set it for "
            "you.\n\n"
            "Which means a bulk `delete(Post)` leaves the link table "
            "populated, and nothing complains until a later join returns "
            "rows for a post that no longer exists."
        ),
        "tags": ["sql", "sqlalchemy"],
        "author": 3,
    },
    {
        "title": "A model behind Form() is the same idea as a model in the body",
        "summary": (
            "Six form fields as six parameters is plumbing. One model is "
            "a description of what the browser sent."
        ),
        "content": (
            "`Annotated[PostFormInput, Form()]` and `Annotated[PageParams,"
            " Query()]` are the same move at two different edges: the "
            "shape lives in a model, the route asks for the model.\n\n"
            "The raw input model is deliberately all-strings and "
            "all-optional. An empty form is a person's mistake to show "
            "back, not a programming error to raise on."
        ),
        "tags": ["fastapi", "pydantic"],
    },
    {
        "title": "A validator that forgets to return sets the field to None",
        "summary": (
            "It does not fail loudly. It succeeds quietly, with your data "
            "replaced by nothing."
        ),
        "content": (
            "Pydantic takes whatever the validator returns as the new "
            "value. Fall off the end without a `return` and that value is "
            "`None`.\n\n"
            "If the field is optional, nothing complains — not at "
            "validation, not at insert, not until something downstream "
            "reads it and finds a hole."
        ),
        "tags": ["pydantic", "python"],
        "author": 4,
    },
    {
        "title": "Response models are a filter, not just documentation",
        "summary": (
            "The password hash does not leak because the schema never "
            "mentioned it. That is the actual mechanism."
        ),
        "content": (
            "It is tempting to read `response_model` as a docs feature. "
            "It is a serialisation contract: fields not on the model do "
            "not go out, whatever the ORM object happens to hold.\n\n"
            "Which is why *public* and *private* views of a user are two "
            "classes and not one class with a flag."
        ),
        "tags": ["fastapi", "pydantic", "security"],
    },
    {
        "title": "None means 'not sent', and that is a decision",
        "summary": (
            "For PATCH, `exclude_unset` distinguishes an omitted field "
            "from a null. Whether you want that distinction is the "
            "question."
        ),
        "content": (
            "None of the post's columns is nullable, so a null could not "
            "mean *set it to null* — there is nothing sensible for it to "
            "do. Treating both as *leave it alone* is therefore free.\n\n"
            "On a schema with genuinely nullable columns it is not free, "
            "and the two cases have to be told apart on purpose."
        ),
        "tags": ["pydantic", "http"],
        "author": 1,
    },
    {
        "title": "Tags replace, they do not merge",
        "summary": (
            "Sending `[]` clears them, omitting the key keeps them, and "
            "there is no way to add one without naming the rest."
        ),
        "content": (
            "That is the usual trade for keeping a collection field "
            "simple. The alternative is an add/remove sub-resource, which "
            "is two more endpoints and a second way to be wrong.\n\n"
            "Whichever you pick, write it in the schema docstring. This "
            "is exactly the kind of rule a caller discovers by losing "
            "data."
        ),
        "tags": ["http", "pydantic"],
    },
    {
        "title": "Normalising tags in one place is not premature",
        "summary": (
            "Strip, lowercase, de-duplicate. Do it in two schemas and "
            "they drift within a month."
        ),
        "content": (
            "Create and update both accept tags, and both have to agree "
            "on what *Python* and *python* are. One function, imported "
            "twice.\n\n"
            "It lives with the schemas, not with a router: no session, no "
            "request, nothing an interface owns. Putting it in a router "
            "once made schemas import a router, and the import cycle took "
            "the whole application down."
        ),
        "tags": ["pydantic", "python"],
        "author": 2,
    },
    {
        "title": "dict.fromkeys keeps the order sorted() throws away",
        "summary": (
            "De-duplicating with a set is one character shorter and loses "
            "the order the person typed."
        ),
        "content": (
            "Dictionaries have preserved insertion order since 3.7, and "
            "`list(dict.fromkeys(items))` is the idiomatic ordered "
            "de-duplication.\n\n"
            "For tags the order is the author's emphasis. Sorting them "
            "alphabetically is a decision, not a cleanup."
        ),
        "tags": ["python", "internals"],
        "author": 5,
    },
    {
        "title": "What actually happens when a dict resizes",
        "summary": (
            "Two-thirds full, powers of two, and one unlucky insert that "
            "pays for rehashing the whole table."
        ),
        "content": (
            "The cost is amortised, which is a real guarantee about "
            "averages and no guarantee at all about the insert you are "
            "timing.\n\n"
            "If you know the size, say so up front. If you are "
            "benchmarking, this is one of the reasons a single run tells "
            "you nothing."
        ),
        "tags": ["python", "internals"],
        "author": 3,
    },
    {
        "title": "Threads didn't make it faster. Processes did.",
        "summary": (
            "The same tool, two halves of one script, two opposite "
            "results. The GIL explains both."
        ),
        "content": (
            "Resizing twelve images is CPU work, and threads take turns "
            "holding the interpreter lock — so twelve threads did the "
            "work of roughly one, plus overhead.\n\n"
            "The download half of the same script sped up cleanly, "
            "because waiting on a socket releases the lock. Same "
            "concurrency, opposite outcome, and the difference is what "
            "the work is made of."
        ),
        "tags": ["async", "python", "internals"],
    },
    {
        "title": "Pillow is synchronous and it does not care about your loop",
        "summary": (
            "A 300×300 resize is not free, and it blocks every other "
            "request while it runs."
        ),
        "content": (
            "`run_in_threadpool` is the whole fix: the resize goes to a "
            "worker thread and the event loop keeps answering.\n\n"
            "This is the case where the GIL is on your side. Pillow "
            "releases it around the C work, so the thread genuinely "
            "overlaps with the loop instead of taking turns with it."
        ),
        "tags": ["async", "python", "fastapi"],
        "author": 4,
    },
    {
        "title": "await inside a loop is not concurrency",
        "summary": (
            "Ten awaited calls one after another take as long as ten "
            "calls one after another. Which is to say: the same."
        ),
        "content": (
            "`await` means *stop here until this finishes*. Writing it "
            "inside a `for` gives you sequential code with extra "
            "syntax.\n\n"
            "`asyncio.gather` is where the overlap comes from. Then the "
            "question becomes whether the thing on the other end wants "
            "ten simultaneous requests, which is a different problem and "
            "a more interesting one."
        ),
        "tags": ["async", "python"],
    },
    {
        "title": "A blocking driver in an async route is worse than no async",
        "summary": (
            "The syntax says concurrent, the driver says one at a time, "
            "and the loop stops for every query."
        ),
        "content": (
            "`async def` on the route does nothing for you if the "
            "database call underneath is synchronous — it just moves the "
            "blocking into the loop's own thread, where it hurts most.\n\n"
            "Either use an async driver, or keep the route `def` and let "
            "the framework put it in a thread pool. The middle option is "
            "the only one that is actually wrong."
        ),
        "tags": ["async", "sqlalchemy", "fastapi"],
        "author": 1,
    },
    {
        "title": "greenlet is why SQLAlchemy's async works at all",
        "summary": (
            "An extra dependency you did not ask for, doing the thing "
            "that makes the API possible."
        ),
        "content": (
            "The ORM's internals are deeply synchronous. Rewriting them "
            "was not on the table, so the async layer runs them inside a "
            "greenlet and hands control back at the I/O boundary.\n\n"
            "Which is why *greenlet not installed* shows up as a runtime "
            "error in a place that has nothing to do with greenlets."
        ),
        "tags": ["async", "sqlalchemy", "internals"],
        "author": 5,
    },
    {
        "title": "Why you can't filter a window function in WHERE",
        "summary": (
            "The column is defined four lines above the error. The "
            "problem is not where it is, but when it is evaluated."
        ),
        "content": (
            "WHERE runs before the window functions do — it is choosing "
            "which rows exist, and a rank over those rows cannot be known "
            "yet.\n\n"
            "Wrap it in a CTE or a subquery and filter outside. The "
            "ordering of clauses in SQL is not the order they run in, and "
            "this is the error that teaches it."
        ),
        "tags": ["sql"],
        "author": 2,
    },
    {
        "title": "Half your indexes are the ones you never wrote",
        "summary": (
            "A unique constraint builds one. A primary key builds one. "
            "Then somebody adds a third by hand on the same column."
        ),
        "content": (
            "It is not an error, so nothing tells you. The duplicate just "
            "gets maintained on every write, forever.\n\n"
            "Read what the schema already created before adding to it. "
            "The migration that removes a redundant index is one of the "
            "cheapest wins there is."
        ),
        "tags": ["sql", "sqlalchemy"],
    },
    {
        "title": "Path parameters identify, query parameters modify",
        "summary": (
            "`/posts/12` is a thing. `?page=2&per_page=10` is a question "
            "about how you want it."
        ),
        "content": (
            "The rule falls out of what a URL means: the path names a "
            "resource, and the same resource under a different query is "
            "still that resource.\n\n"
            "It also decides where the 404 lives. A path that names "
            "nothing is not found; a query that filters everything out is "
            "an empty page, which is a perfectly good 200."
        ),
        "tags": ["http", "fastapi"],
        "author": 3,
    },
    {
        "title": "An empty page is a 200",
        "summary": (
            "No results is an answer. 404 means the address named nothing "
            "— not that the list came back short."
        ),
        "content": (
            "A tag with no posts is arguably not found. A filter that "
            "matched nothing is definitely found, and empty.\n\n"
            "Confusing the two makes clients write error handling for a "
            "normal outcome, which is how *catch everything and log it* "
            "gets into a codebase."
        ),
        "tags": ["http"],
        "author": 5,
    },
    {
        "title": "303 after a form post, not 302",
        "summary": (
            "The status you pick decides whether refresh re-submits. "
            "Browsers have opinions and they are not the same opinions."
        ),
        "content": (
            "303 says *go and GET this other thing*, which is exactly "
            "what you mean after a successful POST. It also makes the "
            "back button behave.\n\n"
            "302 historically meant something else and got implemented "
            "inconsistently. When you know you mean *see other*, say "
            "*see other*."
        ),
        "tags": ["http"],
        "author": 4,
    },
    {
        "title": "The page is a shell and the script fills it",
        "summary": (
            "Sign-in, registration and the profile render empty on "
            "purpose. The token lives where Jinja cannot see it."
        ),
        "content": (
            "It sits in `localStorage`, which is the browser's, not the "
            "server's. So those three pages come back as structure and "
            "the page's own script calls the API for the rest.\n\n"
            "Every other page is rendered whole by the server. Mixing the "
            "two on one page is where the confusing bugs live."
        ),
        "tags": ["fastapi", "http"],
    },
    {
        "title": "A form POST carries no Authorization header",
        "summary": (
            "Which is why the create-post route is unreachable from a "
            "browser, and why it is still in the code."
        ),
        "content": (
            "The token is in `localStorage`, and a plain form submission "
            "cannot attach it. So the dependency can never be satisfied "
            "on that path and the page's script posts to the API "
            "instead.\n\n"
            "Moving the token to a cookie brings the route back with no "
            "change to it. That is a property of where the token lives, "
            "not of the route — so the route stays."
        ),
        "tags": ["fastapi", "security"],
        "author": 1,
    },
    {
        "title": "Errors should answer in the language of the caller",
        "summary": (
            "A browser wants a page. A script wants JSON. Same exception, "
            "two renderings, decided by the path."
        ),
        "content": (
            "Handlers on the application check whether the path starts "
            "with `/api/` and either delegate to the framework's JSON "
            "handler or render the error template with the original "
            "status code.\n\n"
            "The status is the part people get wrong: an error page "
            "returned as 200 is a lie that caches and crawlers both "
            "believe."
        ),
        "tags": ["fastapi", "http"],
    },
    {
        "title": "uv, ruff and pyrefly replaced four tools in an afternoon",
        "summary": (
            "What the switch actually changed, and the places where the "
            "old ones still know something the new ones do not."
        ),
        "content": (
            "The speed is the headline and the boring part is better: one "
            "lockfile, one config section, one command that a new "
            "contributor can run without reading anything.\n\n"
            "The cost is that the ecosystem is younger. Every so often a "
            "rule is wrong for your framework, and you need to know why "
            "you are ignoring it rather than just ignoring it."
        ),
        "tags": ["tooling", "python"],
        "author": 2,
    },
    {
        "title": "A silenced rule needs a reason next to it",
        "summary": (
            "`# noqa` with nothing after it is a decision nobody can "
            "review, including you in four months."
        ),
        "content": (
            "The useful form names what breaks: what the rule wanted, "
            "what happened when it was followed, and how it was observed. "
            "A reproduction in a comment beats an opinion in a comment.\n\n"
            "It also makes the exception removable. When the tool learns "
            "better, someone can check whether the reason still holds."
        ),
        "tags": ["tooling", "python"],
        "author": 5,
    },
    {
        "title": "The test that passed against yesterday's server",
        "summary": (
            "A stray process on the usual port answered, and the suite "
            "went green against code that no longer existed."
        ),
        "content": (
            "A fixed port is a shared resource, and nothing in the test "
            "checks that the thing answering is the thing it started.\n\n"
            "Ask the operating system for a free port instead. It is two "
            "lines, and it turns a class of impossible-to-reproduce "
            "green runs into ordinary ones."
        ),
        "tags": ["testing", "python"],
        "author": 3,
    },
    {
        "title": "Name test data after the test that asked for it",
        "summary": (
            "A failed run that says `pm_user_1785412345678` has told you "
            "nothing about who that was."
        ),
        "content": (
            "Building the username out of the node name costs one line "
            "and makes the leftover rows self-explanatory. When something "
            "fails halfway, the database itself is the log.\n\n"
            "Same argument as naming a fixture after its purpose rather "
            "than its type. The failure output is a user interface."
        ),
        "tags": ["testing", "python"],
    },
    {
        "title": "An API test suite must not leave a diff",
        "summary": (
            "Running the write endpoints against the development database "
            "is how a test run ends up in a commit."
        ),
        "content": (
            "The run gets its own database in a temporary directory, "
            "seeded from scratch, and thrown away afterwards. Uploaded "
            "files go with it.\n\n"
            "The tell is `git status` after a green run. If it is not "
            "empty, the suite is writing somewhere it should not be."
        ),
        "tags": ["testing", "tooling"],
        "author": 4,
    },
    {
        "title": "You made it to the last page",
        "summary": (
            "The oldest post in the database, which means the pagination "
            "works. Hello from the far end of the list."
        ),
        "content": (
            "This one exists to be found. If you are reading it, the "
            "offset arithmetic is right, the ordering is total, and "
            "nothing got skipped or repeated on the way down — which is "
            "three bugs that did not happen.\n\n"
            "It is also the honest test of the *last page* link, the one "
            "that is off by one in roughly half of the implementations I "
            "have written."
        ),
        "tags": ["sql", "http"],
    },
]


def avatar(letter: str, colour: tuple[int, int, int]) -> bytes:
    """Нарисовать аватар вместо того, чтобы класть картинки в репозиторий."""
    image = Image.new("RGB", (400, 400), colour)
    draw = ImageDraw.Draw(image)
    draw.text(
        (200, 200),
        letter.upper(),
        anchor="mm",
        fill=(28, 28, 28),
        font=ImageFont.load_default(size=220),
    )
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


async def wipe() -> None:
    """
    Снести всё, что скрипт потом создаст заново.

    Связи из post_tags удаляются явно: у них есть ON DELETE CASCADE, но
    SQLite соблюдает внешние ключи только при PRAGMA foreign_keys = ON, а
    SQLAlchemy её не ставит. Массовый delete(Post) оставил бы висящие
    строки, и следующий join вернул бы посты, которых нет.
    """
    for file in PROFILE_PICS_DIR.glob("*"):
        if file.is_file() and file.name != ".gitkeep":
            file.unlink()

    async with AsyncSessionLocal() as db:
        await db.execute(models.post_tags.delete())
        await db.execute(delete(models.Post))
        await db.execute(delete(models.Tag))
        await db.execute(delete(models.User))
        await db.commit()


async def create_users(client: httpx.AsyncClient) -> list[str]:
    """Зарегистрировать авторов, войти каждым и загрузить аватар. Вернуть токены."""
    tokens: list[str] = []

    for person in USERS:
        created = await client.post(
            "/api/users",
            json={
                "username": person["username"],
                "email": person["email"],
                "password": person["password"],
            },
        )
        created.raise_for_status()
        user_id = created.json()["id"]

        issued = await client.post(
            "/api/users/token",
            data={"username": person["email"], "password": person["password"]},
        )
        issued.raise_for_status()
        token = issued.json()["access_token"]
        tokens.append(token)

        if colour := person.get("colour"):
            uploaded = await client.patch(
                f"/api/users/{user_id}/picture",
                files={
                    "file": (
                        "avatar.png",
                        avatar(person["username"][0], colour),
                        "image/png",
                    )
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            uploaded.raise_for_status()

        mark = "" if person.get("colour") else "  (default picture)"
        print(f"  {person['username']}{mark}")

    return tokens


async def create_posts(client: httpx.AsyncClient, tokens: list[str]) -> None:
    """Создать посты в порядке списка — от новых к старым."""
    for item in POSTS:
        token = tokens[item.get("author", 0)]
        response = await client.post(
            "/api/posts",
            json={
                "title": item["title"],
                "summary": item["summary"],
                "content": item["content"],
                "tags": item["tags"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()


async def arrange_dates_and_pin() -> None:
    """
    Расставить даты и закрепить один пост.

    Дат нет в API — публиковать задним числом посторонний не может, и это
    правильно. Поэтому единственная часть скрипта, которая идёт мимо
    роутов, — вот эта, и идёт она через ORM намеренно.
    """
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(models.Post).order_by(models.Post.id))
        posts = result.scalars().all()

        for index, (post, item) in enumerate(zip(posts, POSTS, strict=True)):
            # Полтора дня между постами и смещение по часам, чтобы
            # временные метки не совпадали: сортировка по дате должна
            # быть однозначной, иначе страницы начнут перекрываться.
            await db.execute(
                update(models.Post)
                .where(models.Post.id == post.id)
                .values(
                    date_posted=now
                    - timedelta(days=index * 1.5, hours=(index * 7) % 24),
                    is_pinned=item.get("pinned", False),
                )
            )

        await db.commit()


async def main() -> None:
    print(f"database: {engine.url}")
    if "--yes" not in sys.argv:
        print("сотрёт всех пользователей, посты, теги и аватары.")
        print("подтвердить: uv run python populate.py --yes")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await wipe()
    print("cleared")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://populate"
    ) as client:
        print(f"\n{len(USERS)} users:")
        tokens = await create_users(client)

        print(f"\n{len(POSTS)} posts...")
        await create_posts(client, tokens)

    await arrange_dates_and_pin()
    await engine.dispose()

    print(f"\ndone: {len(USERS)} users, {len(POSTS)} posts, 1 pinned")


if __name__ == "__main__":
    asyncio.run(main())
