# services

What the application can do, and on what conditions. Both surfaces — JSON
and pages — call these functions, which is why a refusal reads the same
in both.

The `Annotated` dependency aliases live here too, each beside the
function that fills it. So do the two protocols this layer states its
requirements with: `AvatarStorage` and `ResetMailer` are declared by the
code that needs them and satisfied elsewhere, by shape rather than by
inheritance.

::: blog.services.auth

::: blog.services.posts

::: blog.services.users

::: blog.services.avatars

::: blog.services.passwords

::: blog.services.tags
