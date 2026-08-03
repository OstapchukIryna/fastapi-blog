"""A small blogging application, arranged in five layers.

Every layer is a package rather than a module, so a new entity arrives as
a file beside its siblings instead of a section appended to a growing
file. Imports may point downwards or sideways, never up:

    presentation/   HTTP and Jinja: routes, templates, error rendering
    services/       what the application can do, and on what conditions
    schemas/        the shapes data takes at the boundary
    infrastructure/ the database, the ORM classes, files on disk
    core/           settings and cryptography; imports nothing of ours

The rule is enforced rather than described: `tests/test_import_graph.py`
walks the same imports and fails on a cycle, on an upward arrow, and on a
sideways arrow nobody has justified. Both import cycles this project has
had began as a sideways arrow added without thinking.
"""
