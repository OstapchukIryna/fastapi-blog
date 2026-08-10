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
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
