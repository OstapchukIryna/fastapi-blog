from fastapi import APIRouter, Response, status

from blog.core.config import settings
from blog.infrastructure.database import DbSession
from blog.schemas import PostCreate, PostDetail, PostUpdate
from blog.schemas.post import PaginatedPostResponse
from blog.services import posts
from blog.services.auth import CurrentUser
from blog.services.posts import LimitDep, OwnedPost, PostDep, SkipDep

router = APIRouter()


@router.get("", response_model=PaginatedPostResponse)
async def list_posts(
    db: DbSession, skip: SkipDep = 0, limit: LimitDep = settings.posts_per_page
):
    # List all posts
    return await posts.all_posts(db, skip, limit)


# Show one post
@router.get("/{post_id}", response_model=PostDetail)
def get_post(post: PostDep):
    return post


@router.post("", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
async def create_post(data: PostCreate, current_user: CurrentUser, db: DbSession):
    # Protected by CurrentUser: the author is whoever the token belongs to
    return await posts.create(db, data, current_user)


@router.put("/{post_id}", response_model=PostDetail)
async def update_all_post_fields(post: OwnedPost, data: PostCreate, db: DbSession):
    return await posts.replace(db, post, data)


@router.patch("/{post_id}", response_model=PostDetail)
async def update_post_fields(post: OwnedPost, data: PostUpdate, db: DbSession):
    return await posts.apply_changes(db, post, data)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_api(post: OwnedPost, db: DbSession) -> Response:
    await posts.delete(db, post)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
