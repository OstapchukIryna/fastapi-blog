# infrastructure

Where the data lives: the engine, the ORM classes, and files on disk.
This layer knows how things are stored and nothing about why.

Two of its classes exist to satisfy a protocol declared a layer up, and
neither imports it — `DiskAvatars` matches `services.avatars.AvatarStorage`
by shape alone.

::: blog.infrastructure.database

::: blog.infrastructure.models.user

::: blog.infrastructure.models.tag

::: blog.infrastructure.models.post

::: blog.infrastructure.models.reset_password

::: blog.infrastructure.images

::: blog.infrastructure.email
