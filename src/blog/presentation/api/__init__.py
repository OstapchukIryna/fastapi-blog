"""The JSON surface: the documented paths, and the only ones in /openapi.json.

Routes here are thin on purpose. Each one names what it needs, calls a
service, and wraps the result in a response model. Anything longer than
that is a rule, and rules live in services/.
"""

# * One place, so a future version prefix (if one is ever needed) costs one
# * import path per module rather than a rewrite.
API_PREFIX = "/api"
