from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from error_handlers import register_error_handlers
from schemas import PostCreate, PostResponse, PostSummary
from seed import posts
from templating import templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

register_error_handlers(app)


def find_related(current: dict, limit: int = 2) -> tuple[list[dict], str]:
    """
    Подбирает записи по пересечению тегов.

    Заголовок секции возвращается вместе со списком: если общих тегов
    нет, блок не называется Related
    """
    others = [p for p in posts if p["id"] != current["id"]]
    tags = set(current.get("tags", []))

    matched = [
        {"post": p, "shared": sorted(tags & set(p.get("tags", [])))}
        for p in others
        if tags & set(p.get("tags", []))
    ]

    if matched:
        # sort стабильна: при равном числе общих тегов побеждает
        # тот, кто раньше в списке, то есть более свежая запись
        matched.sort(key=lambda m: len(m["shared"]), reverse=True)
        return matched[:limit], "Related"

    return [{"post": p, "shared": []} for p in others[:limit]], "More posts"


def arrange(items: list[dict]) -> dict:
    """
    Раскладывает список на ведущую запись и остальные.

    Если закреплённой записи нет, ведущей становится первая по порядку,
    то есть самая свежая. Шаблон по наличию `pinned` понимает, что
    показывать в метке и как назвать секцию ниже.
    """
    pinned = next((p for p in items if p.get("pinned")), None)
    rest = [p for p in items if p is not pinned]
    lead = pinned or (rest.pop(0) if rest else None)
    return {"pinned": pinned, "lead": lead, "rest": rest}


@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
def home(request: Request):
    return templates.TemplateResponse(
        request, "home.html", {**arrange(posts), "title": "Home"}
    )


@app.get("/posts/{post_id}", include_in_schema=False, name="post_page")
def post_page(request: Request, post_id: int):
    post = next((p for p in posts if p["id"] == post_id), None)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    related, related_label = find_related(post)
    return templates.TemplateResponse(
        request,
        "post.html",
        {
            "post": post,
            "related": related,
            "related_label": related_label,
            "title": post["title"],
            "is_author": True,  # TODO: заменить реальной проверкой при авторизации
        },
    )


@app.get("/tags/{tag}", include_in_schema=False, name="get_tag")
def get_tag(request: Request, tag: str):
    tagged = [p for p in posts if tag in p.get("tags", [])]
    if not tagged:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        )

    return templates.TemplateResponse(
        request,
        "home.html",
        {**arrange(tagged), "filter_tag": tag, "title": f"#{tag}"},
    )


@app.get("/about", include_in_schema=False, name="about")
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {"title": "About"})


@app.get("/login", include_in_schema=False, name="login")
def login(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@app.get("/api/posts", response_model=list[PostSummary])
def get_posts():
    return posts


@app.post(
    "/api/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED
)
def create_post(post: PostCreate):
    new_id = max(p["id"] for p in posts) + 1 if posts else 1
    new_post = {
        "id": new_id,
        "author": post.author,
        "title": post.title,
        "date_posted": "26 Jul 2026",
        "tags": post.tags,
        "summary": post.summary,
        "content": post.content,
    }
    posts.append(new_post)
    return new_post


@app.post("/posts/{post_id}/delete", include_in_schema=False, name="delete_post")
def delete_post(post_id: int):
    post = next((p for p in posts if p["id"] == post_id), None)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    posts.remove(post)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/api/posts/{post_id}", response_model=PostResponse)
def get_post(post_id: int):
    post = next((p for p in posts if p["id"] == post_id), None)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post
