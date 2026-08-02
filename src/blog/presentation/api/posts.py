from fastapi import APIRouter, Response, status

from blog.infrastructure.database import DbSession
from blog.schemas import PostCreate, PostDetail, PostResponse, PostUpdate
from blog.services import posts
from blog.services.auth import CurrentUser
from blog.services.posts import OwnedPost, PostDep

router = APIRouter()


@router.get("", response_model=list[PostResponse])
async def list_posts(db: DbSession):
    # List all posts
    return await posts.list_all(db)


# Show one post
@router.get("/{post_id}", response_model=PostDetail)
def get_post(post: PostDep):
    return post


@router.post("", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
async def create_post(form: PostCreate, current_user: CurrentUser, db: DbSession):
    # Protected by CurrentUser: the author is whoever the token belongs to
    return await posts.create(db, form, current_user)


@router.put("/{post_id}", response_model=PostDetail)
async def update_all_post_fields(post: OwnedPost, form: PostCreate, db: DbSession):
    return await posts.replace(db, post, form)


@router.patch("/{post_id}", response_model=PostDetail)
async def update_post_fields(post: OwnedPost, changes: PostUpdate, db: DbSession):
    return await posts.update(db, post, changes)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_api(post: OwnedPost, db: DbSession) -> Response:
    await posts.delete(db, post)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
