"""The JSON surface: the documented paths, and the only ones in /openapi.json.

Routes here are thin on purpose. Each one names what it needs, calls a
service, and wraps the result in a response model. Anything longer than
that is a rule, and rules live in services/.
"""

# * The version belongs in the path, and in exactly one place. Everything
# * under it moves together, which is the point of a version: a client
# * written against v1 keeps working while v2 is being built beside it.
# *
# * A version is cheap to add now and expensive later — once anything
# * outside this repository depends on an address, the unversioned one has
# * to keep answering forever.
API_PREFIX = "/api/v1"
