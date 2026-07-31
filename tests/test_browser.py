"""
The three journeys that only a browser can check.

Everything the API promises is covered by the Postman collection, which
is faster and easier to read. What is left for here is what the pages do
with those answers: the token in localStorage, the menu that follows it,
and the controls that appear for one person and not another.

Kept to three on purpose. This is the slowest layer, and the one that
breaks for reasons that have nothing to do with the change under test.
"""

import re

from playwright.sync_api import Page, expect

from .conftest import PASSWORD, expired_token


def test_register_then_sign_in_then_publish(page: Page, live_server: str) -> None:
    """
    The whole point of having accounts, start to finish.

    Nothing is set up in advance: the account is made through the form
    the way a person makes one, and the post is written with the token
    that signing in produced. If any link in that chain breaks, this
    fails — which is why it is worth its running time.
    """
    handle = "journey_author"
    email = f"{handle}@example.com"

    page.goto(f"{live_server}/register")

    page.fill("#username", handle)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.fill("#confirmPassword", PASSWORD)
    page.click("#registerForm button[type=submit]")

    # The result window is the confirmation; closing it goes to sign-in.
    expect(page.locator("#successModal")).to_be_visible()
    expect(page.locator("#successMessage")).to_contain_text(handle)
    page.click("#successAction")

    expect(page).to_have_url(re.compile(r"/login$"))

    # Signing in deliberately shows no window: the page you land on is
    # the confirmation. Landing on the front page is the assertion.
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.click("#loginForm button[type=submit]")

    expect(page).to_have_url(f"{live_server}/")
    expect(page.locator("#signOut")).to_be_visible()
    expect(page.locator(".nav-anon")).to_be_hidden()

    page.goto(f"{live_server}/posts/new")
    page.fill("#title", "Written by the browser")
    page.fill("#summary", "A post made through the form, with a real token.")
    page.fill("#content", "## Heading\n\nBody text.")
    page.fill("#tags", "python, testing")
    page.click("#postForm button[type=submit]")

    expect(page.locator("#successModal")).to_be_visible()
    expect(page.locator("#successModalLabel")).to_have_text("Published")
    page.click("#successAction")

    # The post exists, is readable, and belongs to the new account.
    expect(page).to_have_url(re.compile(r"/posts/\d+$"))
    expect(page.locator("h1")).to_have_text("Written by the browser")
    expect(page.locator(".post-meta")).to_contain_text(handle)


def test_expired_token_is_noticed_on_the_profile(
    page: Page, live_server: str, make_account, sign_in
) -> None:
    """
    A token stops working half an hour after it was issued, so this is
    the ordinary end of every session rather than an edge case.

    The page has to notice by itself: nothing tells the browser that the
    token died. The profile is the page that finds out, because it is the
    one that asks the API before it can draw anything.
    """
    account = make_account("owner")
    sign_in(expired_token(account["id"]))

    page.goto(f"{live_server}/profile")

    # Taken to sign in rather than shown an empty profile, and told why.
    expect(page).to_have_url(re.compile(r"/login\?next=%2Fprofile&reason=expired$"))
    expect(page.locator("#loginReasonTitle")).to_have_text("Session expired")

    # The dead token is thrown away rather than left to fail again.
    assert page.evaluate("localStorage.getItem('accessToken')") is None

    # And the menu stops claiming otherwise.
    expect(page.locator(".nav-anon")).to_be_visible()
    expect(page.locator("#signOut")).to_be_hidden()

    # replace, not assign: going back must not bounce off the profile again.
    page.go_back()
    expect(page).not_to_have_url(re.compile(r"/profile$"))


def test_edit_is_offered_to_the_author_only(
    page: Page, live_server: str, api, make_account, sign_in
) -> None:
    """
    Three readers, one post, one control.

    The check is per post rather than per session — holding a token is
    not the same as having written this — so the interesting case is the
    middle one: signed in, entirely legitimate, and still not offered it.
    """
    author = make_account("author")
    stranger = make_account("stranger")

    written = api.post(
        "/api/posts",
        json={
            "title": "Only its author may edit this",
            "summary": "One post, three readers.",
            "content": "Body.",
            "tags": [],
        },
        headers={"Authorization": f"Bearer {author['token']}"},
    )
    written.raise_for_status()
    post_url = f"{live_server}/posts/{written.json()['id']}"

    edit = page.locator("[data-author-only]")

    # A reader with no account.
    page.goto(post_url)
    expect(edit).to_be_hidden()

    # Signed in, but somebody else.
    sign_in(stranger["token"])
    page.goto(post_url)
    expect(page.locator("#signOut")).to_be_visible()
    expect(edit).to_be_hidden()

    # The author.
    sign_in(author["token"])
    page.goto(post_url)
    expect(edit).to_be_visible()
    expect(edit.get_by_role("link", name="Edit")).to_be_visible()
