"""Login-failure throttling shared by all API workers.

Redis is the source of truth in pilot/production so a restart or a second API
worker cannot reset the account/origin quota.  Development and test processes
fall back to a small in-process counter to keep the local API usable without
Redis; that fallback is never enabled for a secure environment.
"""

from __future__ import annotations

import hashlib
import ipaddress
import threading
import time
from dataclasses import dataclass
from typing import Any

from . import config

try:
    import redis
except ImportError:  # pragma: no cover - backend requirements include redis
    redis = None  # type: ignore[assignment]


# Keep the per-identity limit tight while allowing several users behind one
# legitimate NAT to authenticate independently.  The origin quota still caps
# password spraying from a single address.
IDENTITY_MAX_FAILURES = 5
ORIGIN_MAX_FAILURES = 20
# Backwards-compatible name for callers that used the original identity limit.
MAX_FAILURES = IDENTITY_MAX_FAILURES
WINDOW_SECONDS = 300
_KEY_PREFIX = "iddrv:auth:login-failures:v1"
_local_lock = threading.Lock()
_local_failures: dict[str, tuple[int, float]] = {}
_local_inflight: dict[str, tuple[int, float]] = {}

_RESERVE_SCRIPT = """
local function value(key)
    return tonumber(redis.call('GET', key) or '0')
end
local function expiry(key)
    local ttl = tonumber(redis.call('TTL', key))
    return ttl > 0 and ttl or tonumber(ARGV[3])
end
local origin = value(KEYS[1])
local identity = value(KEYS[2])
local origin_inflight = value(KEYS[3])
local identity_inflight = value(KEYS[4])
local origin_limit = tonumber(ARGV[1])
local identity_limit = tonumber(ARGV[2])
if origin + origin_inflight >= origin_limit or identity + identity_inflight >= identity_limit then
    local retry = 0
    if origin + origin_inflight >= origin_limit then retry = math.max(retry, expiry(KEYS[1]), expiry(KEYS[3])) end
    if identity + identity_inflight >= identity_limit then retry = math.max(retry, expiry(KEYS[2]), expiry(KEYS[4])) end
    return {0, math.max(1, retry)}
end
for _, key in ipairs({KEYS[3], KEYS[4]}) do
    local current = redis.call('INCR', key)
    -- EXPIRE on a missing key is a no-op, so increment first. Also repair a
    -- stale key created by an older deployment without a TTL.
    if current == 1 or tonumber(redis.call('TTL', key)) < 0 then
        redis.call('EXPIRE', key, ARGV[3])
    end
end
return {1, 0}
"""

_COMMIT_FAILURE_SCRIPT = """
local function release(key)
    local current = tonumber(redis.call('GET', key) or '0')
    if current > 1 then redis.call('DECR', key) elseif current == 1 then redis.call('DEL', key) end
end
release(KEYS[3])
release(KEYS[4])
local origin = redis.call('INCR', KEYS[1])
local identity = redis.call('INCR', KEYS[2])
if origin == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
if identity == 1 then redis.call('EXPIRE', KEYS[2], ARGV[1]) end
return {origin, identity}
"""

_RELEASE_SCRIPT = """
local function release(key)
    local current = tonumber(redis.call('GET', key) or '0')
    if current > 1 then redis.call('DECR', key) elseif current == 1 then redis.call('DEL', key) end
end
release(KEYS[1])
release(KEYS[2])
return 1
"""

_CLEAR_SUCCESS_SCRIPT = """
local function release(key)
    local current = tonumber(redis.call('GET', key) or '0')
    if current > 1 then redis.call('DECR', key) elseif current == 1 then redis.call('DEL', key) end
end
release(KEYS[3])
release(KEYS[4])
redis.call('DEL', KEYS[2])
return 1
"""


class ThrottleUnavailable(RuntimeError):
    """The shared security counter cannot be reached."""


@dataclass(frozen=True)
class LoginThrottleKey:
    origin: str
    identity: str


def _is_trusted_proxy(peer: str) -> bool:
    try:
        peer_address = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for configured in config.settings.trusted_proxy_ips:
        try:
            if peer_address in ipaddress.ip_network(configured, strict=False):
                return True
        except ValueError:
            # A bad optional entry must not turn an untrusted request into a
            # trusted one (and should not prevent the API from serving traffic).
            continue
    return False


def _first_forwarded_ip(value: str) -> str | None:
    # The gateway supplies the client as the first hop. Do not skip an invalid
    # first value and accept a later, potentially attacker-controlled hop.
    candidate = value.split(",", 1)[0].strip()
    try:
        ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        return None


def client_ip(request: Any) -> str:
    """Resolve the client IP, trusting forwarding headers only from known proxies.

    The web gateway overwrites X-Forwarded-For with the socket peer address.
    X-Real-IP remains supported for compatibility, but both headers are ignored
    when a client connects directly to the API.
    """
    peer = (request.client.host if request.client else "unknown").strip() or "unknown"
    if not _is_trusted_proxy(peer):
        return peer
    forwarded = _first_forwarded_ip(request.headers.get("X-Forwarded-For", ""))
    return forwarded or _first_forwarded_ip(request.headers.get("X-Real-IP", "")) or peer


def _secure_environment() -> bool:
    return config.settings.app_environment in {"pilot", "prod", "production"}


def _normalise_email(email: str) -> str:
    return " ".join(email.strip().casefold().split())


def _key(email: str, client_ip: str) -> LoginThrottleKey:
    identity_digest = hashlib.sha256(_normalise_email(email).encode("utf-8")).hexdigest()
    # IPs are not put in Redis key names verbatim.  Canonicalising addresses
    # also prevents alternate IPv6 spellings from bypassing the origin quota.
    origin_value = client_ip.strip()
    try:
        origin_value = ipaddress.ip_address(origin_value).compressed
    except ValueError:
        pass
    origin_digest = hashlib.sha256(origin_value.encode("utf-8")).hexdigest()
    return LoginThrottleKey(
        origin=f"{_KEY_PREFIX}:ip:{origin_digest}",
        identity=f"{_KEY_PREFIX}:pair:{origin_digest}:{identity_digest}",
    )


def _redis_client() -> Any:
    if redis is None:
        raise ThrottleUnavailable("redis_dependency_unavailable")
    try:
        client = redis.Redis.from_url(
            config.settings.redis_url,
            socket_connect_timeout=config.settings.db_connect_timeout_s,
            socket_timeout=config.settings.db_connect_timeout_s,
            decode_responses=True,
        )
        client.ping()
        return client
    except Exception as exc:  # redis-py exposes several connection exception types
        raise ThrottleUnavailable("redis_unavailable") from exc


def _inflight_key(key: str) -> str:
    return f"{key}:inflight"


def _redis_reserve(client: Any, keys: LoginThrottleKey) -> tuple[bool, int]:
    try:
        result = client.eval(
            _RESERVE_SCRIPT,
            4,
            keys.origin,
            keys.identity,
            _inflight_key(keys.origin),
            _inflight_key(keys.identity),
            ORIGIN_MAX_FAILURES,
            IDENTITY_MAX_FAILURES,
            WINDOW_SECONDS,
        )
        return bool(int(result[0])), max(0, int(result[1]))
    except Exception as exc:
        raise ThrottleUnavailable("redis_unavailable") from exc


def _redis_commit_failure(client: Any, keys: LoginThrottleKey) -> None:
    try:
        client.eval(
            _COMMIT_FAILURE_SCRIPT,
            4,
            keys.origin,
            keys.identity,
            _inflight_key(keys.origin),
            _inflight_key(keys.identity),
            WINDOW_SECONDS,
        )
    except Exception as exc:
        raise ThrottleUnavailable("redis_unavailable") from exc


def _redis_release(client: Any, keys: LoginThrottleKey) -> None:
    try:
        client.eval(
            _RELEASE_SCRIPT,
            2,
            _inflight_key(keys.origin),
            _inflight_key(keys.identity),
        )
    except Exception as exc:
        raise ThrottleUnavailable("redis_unavailable") from exc


def allowed(email: str, client_ip: str) -> tuple[bool, int]:
    """Atomically reserve one authentication attempt and return its delay."""

    keys = _key(email, client_ip)
    try:
        return _redis_reserve(_redis_client(), keys)
    except ThrottleUnavailable:
        if _secure_environment():
            raise
        return _local_reserve(keys)


def record_failure(email: str, client_ip: str) -> None:
    """Commit the reserved attempt as a failure and release its slot."""
    keys = _key(email, client_ip)
    try:
        _redis_commit_failure(_redis_client(), keys)
        return
    except ThrottleUnavailable:
        if _secure_environment():
            raise
        _local_commit_failure(keys)


def release_reservation(email: str, client_ip: str) -> None:
    """Release an attempt that did not produce an authentication result."""
    keys = _key(email, client_ip)
    try:
        _redis_release(_redis_client(), keys)
        return
    except ThrottleUnavailable:
        if _secure_environment():
            raise
        _local_release(keys)


def clear_failure(email: str, client_ip: str) -> None:
    """Release success and clear only this identity's failure quota."""
    keys = _key(email, client_ip)
    try:
        client = _redis_client()
        # The release and identity reset must be one Redis operation. Keep a
        # small compatibility path for the existing minimal test double.
        if hasattr(client, "eval"):
            client.eval(
                _CLEAR_SUCCESS_SCRIPT,
                4,
                keys.origin,
                keys.identity,
                _inflight_key(keys.origin),
                _inflight_key(keys.identity),
            )
        else:
            client.delete(keys.identity)
        return
    except ThrottleUnavailable:
        if _secure_environment():
            raise
        _local_release_and_clear(keys)
    except Exception as exc:
        if _secure_environment():
            raise ThrottleUnavailable("redis_unavailable") from exc
        _local_release_and_clear(keys)


def _local_reserve(keys: LoginThrottleKey) -> tuple[bool, int]:
    now = time.monotonic()
    with _local_lock:
        limits = {keys.origin: ORIGIN_MAX_FAILURES, keys.identity: IDENTITY_MAX_FAILURES}
        blocked_expiries: list[float] = []
        for key in (keys.origin, keys.identity):
            failure_count, failure_expiry = _local_failures.get(key, (0, 0.0))
            inflight_count, inflight_expiry = _local_inflight.get(key, (0, 0.0))
            if failure_expiry <= now:
                failure_count, failure_expiry = 0, 0.0
            if inflight_expiry <= now:
                inflight_count, inflight_expiry = 0, 0.0
            if failure_count + inflight_count >= limits[key]:
                blocked_expiries.append(max(failure_expiry, inflight_expiry))
        if blocked_expiries:
            return False, max(1, int(max(blocked_expiries) - now))
        expiry = now + WINDOW_SECONDS
        for key in (keys.origin, keys.identity):
            count, current_expiry = _local_inflight.get(key, (0, expiry))
            if current_expiry <= now:
                count, current_expiry = 0, expiry
            _local_inflight[key] = (count + 1, current_expiry)
        return True, 0


def _local_release(keys: LoginThrottleKey) -> None:
    with _local_lock:
        for key in (keys.origin, keys.identity):
            count, expiry = _local_inflight.get(key, (0, 0.0))
            if count > 1:
                _local_inflight[key] = (count - 1, expiry)
            else:
                _local_inflight.pop(key, None)


def _local_commit_failure(keys: LoginThrottleKey) -> None:
    now = time.monotonic()
    with _local_lock:
        for key in (keys.origin, keys.identity):
            count, expiry = _local_inflight.get(key, (0, 0.0))
            if count > 1:
                _local_inflight[key] = (count - 1, expiry)
            else:
                _local_inflight.pop(key, None)
            failure_count, failure_expiry = _local_failures.get(key, (0, now + WINDOW_SECONDS))
            if failure_expiry <= now:
                failure_count, failure_expiry = 0, now + WINDOW_SECONDS
            _local_failures[key] = (failure_count + 1, failure_expiry)


def _local_release_and_clear(keys: LoginThrottleKey) -> None:
    with _local_lock:
        for key in (keys.origin, keys.identity):
            count, expiry = _local_inflight.get(key, (0, 0.0))
            if count > 1:
                _local_inflight[key] = (count - 1, expiry)
            else:
                _local_inflight.pop(key, None)
        # Never clear the shared origin quota after one account succeeds.
        _local_failures.pop(keys.identity, None)


def reset_for_tests() -> None:
    """Clear process-local counters; intended for unit tests only."""
    with _local_lock:
        _local_failures.clear()
        _local_inflight.clear()
