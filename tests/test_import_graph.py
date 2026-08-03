"""
Проверка того, что записано словами в docs/architecture.md.

Циклический импорт здесь случался дважды, и оба раза одинаково: общая
вещь, которой ничего не нужно для существования, оказывалась внутри
модуля, у которого зависимости есть, — потому что он первым её попросил.

    normalise_tags жила в routers/tags.py, схемам понадобилось чистить
    теги: schemas -> routers.tags -> routers.posts -> schemas

    SkipDep жил в services/posts.py, тегам понадобился срез:
    services.tags -> services.posts -> services.tags

Ловится это только при запуске приложения, и сообщение указывает не на
плохое ребро, а на его жертву — «cannot import name 'posts_query' from
partially initialized module», хотя виноват был вообще другой файл.
Тесты ниже называют само ребро.

Считается граф *исполняемых* импортов: тела `if TYPE_CHECKING:` не
выполняются и цикла вызвать не могут, поэтому пропускаются. Обратная
сторона — под TYPE_CHECKING можно спрятать импорт, который на самом деле
нужен в рантайме; для FastAPI это обычная ловушка (см. отключённые
TC001-003 в pyproject.toml), и от неё страхует не этот файл, а
test_the_application_imports вместе с прогоном API.
"""

import ast
import os
from collections import defaultdict
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"

# Снизу вверх. Импорт разрешён внутрь своего уровня и на любой уровень
# ниже; наверх — никогда.
LAYERS = {
    "core": 0,
    "infrastructure": 1,
    "schemas": 2,
    "services": 3,
    "presentation": 4,
}
TOP = 5  # blog.main и всё, что не в пакете слоя

# Рёбра внутри одного слоя. Не запрещены — но каждое должно быть
# осознанным, поэтому список явный и с причиной. Оба цикла в истории
# проекта были именно боковыми рёбрами, добавленными не думая.
#
# Проверка на «зависимость или общий словарь»: если бы этих двух
# сущностей не существовало, эта штука имела бы смысл? Срез — да, и
# поэтому он уехал в schemas/pagination.py. get_or_create — нет.
ALLOWED_SIDEWAYS = {
    ("blog.core.security", "blog.core.config"): "подписи нужен секрет",
    (
        "blog.infrastructure.models.post",
        "blog.infrastructure.database",
    ): "Base объявлен там",
    (
        "blog.infrastructure.models.tag",
        "blog.infrastructure.database",
    ): "Base объявлен там",
    (
        "blog.infrastructure.models.user",
        "blog.infrastructure.database",
    ): "Base объявлен там",
    (
        "blog.infrastructure.models.post",
        "blog.infrastructure.models.tag",
    ): "посту нужна таблица связи post_tags",
    (
        "blog.infrastructure.models.post",
        "blog.infrastructure.models.user",
    ): "у поста есть автор",
    (
        "blog.presentation.errors",
        "blog.presentation.web.templating",
    ): "страницу ошибки рисует тот же Jinja",
    (
        "blog.presentation.web.forms",
        "blog.presentation.web.templating",
    ): "форма рисуется шаблоном",
    (
        "blog.presentation.web.pages",
        "blog.presentation.web.forms",
    ): "две страницы показывают форму поста",
    (
        "blog.presentation.web.pages",
        "blog.presentation.web.templating",
    ): "страницы рисуются шаблонами",
    ("blog.schemas.post", "blog.schemas.tag"): "правила тегов общие для всех схем",
    ("blog.schemas.post", "blog.schemas.user"): "в ответе про пост есть автор",
    ("blog.services.posts", "blog.services.auth"): "владение — вопрос о текущем юзере",
    ("blog.services.posts", "blog.services.tags"): "сохранить пост значит создать теги",
    ("blog.services.users", "blog.services.auth"): "владение — вопрос о текущем юзере",
}


def module_name(path: Path) -> str:
    name = str(path.relative_to(SRC)).removesuffix(".py").replace(os.sep, ".")
    return name.removesuffix(".__init__")


def layer(module: str) -> int:
    parts = module.split(".")
    return LAYERS.get(parts[1], TOP) if len(parts) > 1 else TOP


def runtime_imports(tree: ast.AST) -> list[ast.stmt]:
    """Всё, кроме тел `if TYPE_CHECKING:` — они никогда не исполняются."""
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
    """
    Module to the modules it imports at import time.

    `from blog.services import tags` и `from blog.services.tags import
    get_or_create` — одно и то же ребро, поэтому имя разрешается до
    файла, если такой файл есть.
    """
    modules = {module_name(path): path for path in sorted(SRC.rglob("*.py"))}
    edges: dict[str, set[str]] = defaultdict(set)

    for name, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in runtime_imports(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "blog"
            ):
                for alias in node.names:
                    submodule = f"{node.module}.{alias.name}"
                    target = submodule if submodule in modules else node.module
                    if target != name:
                        edges[name].add(target)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in modules and alias.name != name:
                        edges[name].add(alias.name)

    assert modules, f"в {SRC} не нашлось ни одного модуля — проверь путь"
    return dict(edges)


def test_no_import_cycles(graph):
    """
    Ни одного цикла — включая те, что идут через третий модуль.

    Обход в глубину, а не поиск компонент связности: нужен сам путь,
    иначе сообщение будет не полезнее исходного ImportError.
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

    assert not cycles, "циклический импорт:\n" + "\n".join(
        "  " + " -> ".join(cycle) for cycle in cycles
    )


def test_no_upward_imports(graph):
    """Стрелки только вниз или вбок. Слой ниже не знает о слое выше."""
    upward = [
        f"  {source} ({layer(source)}) -> {target} ({layer(target)})"
        for source, targets in sorted(graph.items())
        for target in sorted(targets)
        if layer(source) < layer(target)
    ]

    assert not upward, (
        "импорт наверх — нижний слой не должен знать о верхнем:\n"
        + "\n".join(upward)
        + "\n\nобычно это значит, что общая вещь лежит слишком высоко: "
        "спроси, что ей нужно для существования, и положи её туда."
    )


def test_sideways_imports_are_declared(graph):
    """
    Каждое ребро внутри слоя объявлено в ALLOWED_SIDEWAYS.

    Пакетный __init__ не в счёт: импорт своих же подмодулей — это то,
    что делает пакет пакетом, а не зависимость между соседями.
    """
    found = {
        (source, target)
        for source, targets in graph.items()
        for target in targets
        if layer(source) == layer(target)
        and not target.startswith(f"{source}.")  # __init__ пакета
    }

    undeclared = sorted(found - set(ALLOWED_SIDEWAYS))
    assert not undeclared, (
        "боковой импорт без объяснения:\n"
        + "\n".join(f"  {a} -> {b}" for a, b in undeclared)
        + "\n\nесли это настоящая зависимость — впиши её в ALLOWED_SIDEWAYS "
        "с причиной. Если общий словарь — ему место слоем ниже, а не у соседа."
    )

    stale = sorted(set(ALLOWED_SIDEWAYS) - found)
    assert not stale, "в ALLOWED_SIDEWAYS осталось лишнее:\n" + "\n".join(
        f"  {a} -> {b}" for a, b in stale
    )


def test_the_application_imports(monkeypatch):
    """
    Последняя проверка — та, которую граф по AST дать не может.

    Порядок исполнения, побочные эффекты в __init__, импорт внутри
    функции: всё это ловится только настоящим импортом приложения.
    """
    monkeypatch.setenv("SECRET_KEY", "import-graph-test-secret-long-enough-32")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    from blog.main import app

    assert app.title
