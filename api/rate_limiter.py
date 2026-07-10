"""
Single shared slowapi Limiter instance. Import this everywhere a route
needs @limiter.limit(...) -- do NOT create a second Limiter() elsewhere
(e.g. directly in a route file); slowapi expects one shared instance
wired to app.state.limiter (done in api/main.py) and referenced by the
same object from every @limiter.limit(...) decorator, not lookalike
separate instances.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
