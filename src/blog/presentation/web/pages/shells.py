"""Pages the server renders without reading anything.

Six routes, one line each. Together they are the answer to a question the
other modules kept raising: why does a page that shows a profile take no
user, and why does sign-in not sign anybody in? Because the token lives in
localStorage, where the server cannot see it. These routes return a shell,
and the page's own script fills it from /api.

Grouped rather than scattered so that "this page has no data on purpose"
is said once, here, instead of route by route.
"""

from fastapi import APIRouter, Request, Response

from blog.presentation.web.templating import templates

router = APIRouter()


@router.get("/about", name="about")
def about(request: Request) -> Response:
    """Render the static about page.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered page.
    """
    return templates.TemplateResponse(request, "about.html", {"title": "About"})


@router.get("/profile", name="profile")
def profile(request: Request) -> Response:
    """Render the profile shell.

    Deliberately empty of data: the token lives in localStorage, so the
    server cannot know whose profile this is. The page's own script
    fetches /api/v1/users/me and fills it in.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered shell.
    """
    return templates.TemplateResponse(request, "profile.html", {"title": "Profile"})


@router.get("/login", name="login")
def login_page(request: Request) -> Response:
    """Render the sign-in form.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered page. The form posts to the API from the
            browser rather than to this route, because the answer is a
            token the server has nowhere to put.
    """
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@router.get("/register", name="register")
def register_page(request: Request) -> Response:
    """Render the registration form.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered page.
    """
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})


# ! Named *_page, unlike the other pages here. Route names are unique
# ! across the whole application, and the API endpoints of the same
# ! purpose already hold `forgot_password` and `reset_password` — with
# ! the short names, url_for in a template silently returned /api/… .
@router.get("/forgot-password", include_in_schema=False, name="forgot_password_page")
async def forgot_password_page(request: Request) -> Response:
    """Render the form that asks for a reset link.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered page. Like sign-in, it is a shell: the
            form posts to the API, because the answer is deliberately the
            same whether or not the address is known and the server has
            no session in which to remember which was asked.
    """
    return templates.TemplateResponse(
        request, "forgot_password.html", {"title": "Forgot password"}
    )


@router.get("/reset-password", include_in_schema=False, name="reset_password_page")
async def reset_password_page(request: Request) -> Response:
    """Render the form that sets a new password from an emailed link.

    The token is not read here. It stays in the query string and is sent
    by the page's own script, so it never reaches the server as part of a
    page request — where it would end up in access logs and in the
    Referer header of anything the page loads.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the rendered page.
    """
    response = templates.TemplateResponse(
        request, "reset_password.html", {"title": "Reset password"}
    )
    # Security measure
    response.headers["Refferer-Policy"] = "no-refferer"
    return response
