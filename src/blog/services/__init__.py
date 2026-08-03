"""What the application can do, and on what conditions.

Everything that once sat in route bodies lives here: the queries, the
rules, the refusals, and the transaction. The point is that both surfaces
— JSON and pages — call the same functions, so "this post is not yours"
is one place in the code rather than two similar pieces that drift.

The Annotated dependency aliases live here too (PostDep, OwnedPost,
CurrentUser and the rest), each next to the function that fills it. There
is deliberately no central wiring module: a route names what it needs in
its signature, and that is enough.
"""
