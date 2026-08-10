"""Enforcing what docs/architecture.md only describes.

This project has had an import cycle twice, the same way both times:
something shared, which needs nothing in order to exist, ended up inside
a module that does have dependencies — because that module asked for it
first.

    normalise_tags lived in routers/tags.py, and schemas needed to clean
    tags:  schemas -> routers.tags -> routers.posts -> schemas

    SkipDep lived in services/posts.py, and tags needed a slice:
    services.tags -> services.posts -> services.tags

Both were found by starting the application, and both times the error
named the victim rather than the bad edge — "cannot import name
'posts_query' from partially initialized module" pointed at a file that
had done nothing wrong. The tests below name the edge.

The graph is of imports that actually run. Bodies of `if TYPE_CHECKING:`
are skipped, because they never execute and cannot cause a cycle. The
trade-off is that a runtime import can be hidden under TYPE_CHECKING and
this file will not notice; for FastAPI that is a well-known trap (see the
disabled TC001-003 in pyproject.toml), and what guards against it is
test_the_application_imports together with the API run.
"""

import ast
import os
from collections import defaultdict
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"

# * Bottom to top. An import may stay inside its own level or go to any
# * level below it. Upwards: never.
LAYERS = {
    "core": 0,
    "infrastructure": 1,
    "schemas": 2,
    "services": 3,
    "presentation": 4,
}
TOP = 5  # blog.main, and anything not inside a layer package

# Edges inside one layer. Not forbidden — but each one should be a
# decision, so the list is explicit and every entry carries its reason.
# Both cycles in this project's history were sideways edges added without
# thinking.
#
# * The test for "real dependency or shared vocabulary": if neither of
# * these two entities existed, would the thing still make sense? A slice
# * would — which is why it moved to schemas/pagination.py. get_or_create
# * would not, which is why posts -> tags stays.
ALLOWED_SIDEWAYS = {
    ("blog.core.security", "blog.core.config"): "signing needs the secret",
    (
        "blog.core.security",
        "blog.core.errors",
    ): "Unauthorized is a refusal, not a crypto primitive",
    (
        "blog.core.logging",
        "blog.core.config",
    ): "configure_logging reads environment and log_level off Settings",
    (
        "blog.infrastructure.models.post",
        "blog.infrastructure.database",
    ): "Base is declared there",
    (
        "blog.infrastructure.models.tag",
        "blog.infrastructure.database",
    ): "Base is declared there",
    (
        "blog.infrastructure.models.user",
        "blog.infrastructure.database",
    ): "Base is declared there",
    (
        "blog.infrastructure.models.user",
        "blog.infrastructure.images",
    ): "image_path defers to AWSAvatars for how a storage URL is shaped, "
    "rather than keeping a second copy of that knowledge here",
    (
        "blog.infrastructure.models.reset_password",
        "blog.infrastructure.database",
    ): "Base is declared there",
    (
        "blog.infrastructure.models.post",
        "blog.infrastructure.models.tag",
    ): "a post needs the post_tags association",
    (
        "blog.infrastructure.models.post",
        "blog.infrastructure.models.user",
    ): "a post has an author",
    (
        "blog.presentation.api.users",
        "blog.presentation.api.mail",
    ): "the reset route supplies the mailer the service asks for",
    (
        "blog.presentation.errors",
        "blog.presentation.web.templating",
    ): "the error page uses the same Jinja",
    (
        "blog.presentation.web.forms",
        "blog.presentation.web.templating",
    ): "the form is drawn by a template",
    (
        "blog.presentation.web.pages.listings",
        "blog.presentation.web.pages.feed",
    ): "every list page has a load-more button",
    (
        "blog.presentation.web.pages.listings",
        "blog.presentation.web.templating",
    ): "pages are drawn by templates",
    (
        "blog.presentation.web.pages.posts",
        "blog.presentation.web.forms",
    ): "two pages show the post form",
    (
        "blog.presentation.web.pages.posts",
        "blog.presentation.web.templating",
    ): "pages are drawn by templates",
    (
        "blog.presentation.web.pages.shells",
        "blog.presentation.web.templating",
    ): "pages are drawn by templates",
    (
        "blog.schemas.post",
        "blog.schemas.tag",
    ): "the tag rules are shared by every schema",
    ("blog.schemas.post", "blog.schemas.user"): "a post response embeds its author",
    (
        "blog.services.posts",
        "blog.services.auth",
    ): "ownership is a question about the current user",
    (
        "blog.services.posts",
        "blog.services.tags",
    ): "storing a post means creating its tags",
    (
        "blog.services.users",
        "blog.services.auth",
    ): "ownership is a question about the current user",
}


def module_name(path: Path) -> str:
    name = str(path.relative_to(SRC)).removesuffix(".py").replace(os.sep, ".")
    return name.removesuffix(".__init__")


def layer(module: str) -> int:
    parts = module.split(".")
    return LAYERS.get(parts[1], TOP) if len(parts) > 1 else TOP


def runtime_imports(tree: ast.AST) -> list[ast.AST]:
    """Every node except the bodies of `if TYPE_CHECKING:`.

    Args:
        tree (ast.AST): a parsed module.

    Returns:
        list[ast.AST]: nodes that run when the module is imported.
    """
    deferred: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        checks_typing = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if checks_typing:
            deferred.update(id(inner) for body in node.body for inner in ast.walk(body))

    return [node for node in ast.walk(tree) if id(node) not in deferred]


@pytest.fixture(scope="session")
def graph() -> dict[str, set[str]]:
    """Map each module to the modules it imports at import time.

    `from blog.services import tags` and `from blog.services.tags import
    get_or_create` are the same edge, so a name is resolved down to a
    file whenever a file by that name exists.

    Returns:
        dict[str, set[str]]: module name to the modules it imports.
    """
    modules = {module_name(path): path for path in sorted(SRC.rglob("*.py"))}
    edges: dict[str, set[str]] = defaultdict(set)

    for name, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in runtime_imports(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("blog"):
                # `node.module` is Optional on the AST, but a relative
                # import (`from . import x`) never starts with "blog", so
                # the branch above has already excluded None.
                module = node.module or ""
                for alias in node.names:
                    submodule = f"{module}.{alias.name}"
                    target = submodule if submodule in modules else module
                    if target != name:
                        edges[name].add(target)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in modules and alias.name != name:
                        edges[name].add(alias.name)

    assert modules, f"no modules found under {SRC} — check the path"
    return dict(edges)


def test_no_import_cycles(graph):
    """No cycles, including ones that travel through a third module.

    Depth-first rather than strongly-connected components, because the
    path itself is the useful part: without it the message would be no
    more help than the original ImportError.

    Args:
        graph (dict[str, set[str]]): the import graph.
    """
    cycles: list[list[str]] = []
    done: set[str] = set()
    path: list[str] = []

    def walk(module: str) -> None:
        if module in path:
            cycles.append(path[path.index(module) :] + [module])
            return
        if module in done:
            return
        done.add(module)
        path.append(module)
        for target in sorted(graph.get(module, ())):
            walk(target)
        path.pop()

    for module in sorted(graph):
        walk(module)

    assert not cycles, "import cycle:\n" + "\n".join("  " + " -> ".join(cycle) for cycle in cycles)


def test_no_upward_imports(graph):
    """Arrows point down or sideways, never up.

    Args:
        graph (dict[str, set[str]]): the import graph.
    """
    upward = [
        f"  {source} ({layer(source)}) -> {target} ({layer(target)})"
        for source, targets in sorted(graph.items())
        for target in sorted(targets)
        if layer(source) < layer(target)
    ]

    assert not upward, (
        "import pointing up — a lower layer must not know an upper one:\n"
        + "\n".join(upward)
        + "\n\nusually this means a shared thing is sitting too high: ask what it "
        "needs in order to exist, and put it there."
    )


def test_sideways_imports_are_declared(graph):
    """Every edge inside a layer is declared in ALLOWED_SIDEWAYS.

    A package's own __init__ does not count: importing its submodules is
    what makes it a package, not a dependency between siblings.

    Args:
        graph (dict[str, set[str]]): the import graph.
    """
    found = {
        (source, target)
        for source, targets in graph.items()
        for target in targets
        if layer(source) == layer(target)
        and not target.startswith(f"{source}.")  # a package's own __init__
    }

    undeclared = sorted(found - set(ALLOWED_SIDEWAYS))
    assert not undeclared, (
        "sideways import with no reason given:\n"
        + "\n".join(f"  {a} -> {b}" for a, b in undeclared)
        + "\n\nif this is a real dependency, add it to ALLOWED_SIDEWAYS with its "
        "reason. If it is shared vocabulary, it belongs a layer down, not "
        "next door."
    )

    stale = sorted(set(ALLOWED_SIDEWAYS) - found)
    assert not stale, "ALLOWED_SIDEWAYS still lists edges that are gone:\n" + "\n".join(
        f"  {a} -> {b}" for a, b in stale
    )


def test_the_application_imports(monkeypatch):
    """The check an AST cannot give: import the application for real.

    Execution order, side effects in a package __init__, an import inside
    a function — none of that is visible in a static graph.

    Args:
        monkeypatch: pytest's environment patcher; the settings refuse to
            load without a secret, and DATABASE_URL has no default.
    """
    monkeypatch.setenv("SECRET_KEY", "import-graph-test-secret-long-enough-32")
    # Never connected to — create_async_engine only parses the URL — but it
    # has to name a driver that is installed, and it must not be the real
    # database in case anything here ever does open a connection.
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://import:graph@127.0.0.1:1/none")

    from blog.main import app

    assert app.title
