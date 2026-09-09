"""Non-waiting process-local compute quota shared by readiness and replay.

Only active authenticated user IDs are retained (at most GLOBAL_LIMIT entries).
No payload IDs, session IDs, identity metrics or idle-history cache.
"""
from contextlib import contextmanager
from threading import Lock
from fastapi import HTTPException

GLOBAL_LIMIT = 2
PER_IDENTITY_LIMIT = 1
_lock = Lock()
_active = {}


@contextmanager
def admit(identity):
    key = identity.user_id
    with _lock:
        if sum(_active.values()) >= GLOBAL_LIMIT or _active.get(key, 0) >= PER_IDENTITY_LIMIT:
            raise HTTPException(429, 'summary6_compute_busy', headers={'Retry-After': '1'})
        _active[key] = _active.get(key, 0) + 1
    try:
        yield
    finally:
        with _lock:
            remaining = _active[key] - 1
            if remaining:
                _active[key] = remaining
            else:
                del _active[key]
