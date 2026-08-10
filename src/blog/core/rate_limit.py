"""Request-rate limiting: one bucket per caller address, shared app-wide.

Core rather than presentation: main.py needs it to wire up the middleware
and exception handler, and a route needs it to tighten its own limit —
two callers on either side of presentation/api, which is what a shared
instance one layer down is for.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# ! In-memory: correct for the one worker process this actually runs as.
# ! Several uvicorn workers would each keep their own count, silently
# ! multiplying the real limit — the fix then is a Redis-backed storage_uri,
# ! not a code change here.
#
# ! default_limits only reaches ordinary FastAPI routes, not /static —
# ! checked directly: 70 requests in a row to the same static file all
# ! answered 200, while the same count against an undecorated API route
# ! hit 429 at request 61. SlowAPIMiddleware tracks routes FastAPI itself
# ! resolves; a StaticFiles mount handles its own routing beneath that and
# ! is invisible to it. A page loading a dozen assets on reload is not at
# ! risk from this default — nothing further to exempt.
#
# ! get_remote_address reads request.client.host as-is; behind a reverse
# ! proxy that is the proxy's own address unless something upstream has
# ! already rewritten it from X-Forwarded-For. uvicorn does this itself by
# ! default (proxy_headers=True, forwarded_allow_ips="127.0.0.1") — checked
# ! directly by spoofing X-Forwarded-For against a request from localhost —
# ! which is exactly right for nginx and uvicorn on the same host. Move
# ! nginx to a different host and that default IP has to move with it, or
# ! every visitor collapses into one bucket behind the proxy's own address.
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
