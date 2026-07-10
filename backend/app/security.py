"""Local session authentication and role/site authorization.

The pilot deliberately keeps authentication inside the API boundary.  Session
cookies are signed, HttpOnly and short lived; the database session row is used
for revocation when the control-plane migration is present.  Read endpoints
may be inspected anonymously only in the development environment, as a
convenience for the local demo.  Any write or privileged operation always
requires a real session.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends, HTTPException, Request

from .config import settings

try:  # argon2-cffi is included by backend/requirements.txt in deployments.
    from argon2 import PasswordHasher
    from argon2.exceptions import VerificationError, VerifyMismatchError
except ImportError:  # pragma: no cover - only used in minimal local installs
    PasswordHasher = None  # type: ignore[assignment,misc]
    VerificationError = VerifyMismatchError = Exception


ROLES = ("viewer", "analyst", "supervisor", "admin")
ROLE_LEVEL = {role: index for index, role in enumerate(ROLES)}
SESSION_HEADER = "Authorization"


@dataclass(frozen=True)
class Identity:
    user_id: str
    email: str
    display_name: str
    role: str
    site_ids: tuple[int, ...] = ()
    session_id: str | None = None
    anonymous: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def can_access_site(self, site_id: int) -> bool:
        return self.is_admin or site_id in self.site_ids


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _password_hasher():
    if PasswordHasher is None:
        return None
    # Explicit parameters keep the pilot reproducible and Argon2id based.
    return PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    """Return an Argon2id hash; scrypt is a dependency-free safety fallback."""

    hasher = _password_hasher()
    if hasher is not None:
        return hasher.hash(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + _b64(salt) + "$" + _b64(digest)


def verify_password(password: str, encoded: str) -> bool:
    if encoded.startswith("$argon2"):
        hasher = _password_hasher()
        if hasher is None:
            return False
        try:
            return bool(hasher.verify(encoded, password))
        except (VerificationError, VerifyMismatchError, ValueError):
            return False
    if encoded.startswith("scrypt$"):
        try:
            _, salt_b64, digest_b64 = encoded.split("$", 2)
            expected = _unb64(digest_b64)
            actual = hashlib.scrypt(password.encode(), salt=_unb64(salt_b64), n=2**14, r=8, p=1)
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False
    return False


def _sign(payload: bytes) -> str:
    return _b64(hmac.new(settings.session_secret.encode(), payload, hashlib.sha256).digest())


def create_session_token(identity: Identity, *, expires_at: datetime | None = None) -> tuple[str, datetime]:
    expires = expires_at or (datetime.now(timezone.utc) + timedelta(seconds=settings.session_ttl_s))
    payload = {
        "sub": identity.user_id,
        "email": identity.email,
        "name": identity.display_name,
        "role": identity.role,
        "sites": list(identity.site_ids),
        "sid": identity.session_id or secrets.token_urlsafe(18),
        "exp": int(expires.timestamp()),
        "nonce": secrets.token_urlsafe(12),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = _b64(raw)
    return body + "." + _sign(raw), expires


def decode_session_token(token: str) -> Identity | None:
    try:
        body, signature = token.split(".", 1)
        raw = _unb64(body)
        if not hmac.compare_digest(_sign(raw), signature):
            return None
        payload = json.loads(raw.decode("utf-8"))
        if int(payload["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            return None
        role = str(payload.get("role", ""))
        if role not in ROLE_LEVEL:
            return None
        return Identity(
            user_id=str(payload["sub"]),
            email=str(payload.get("email", "")),
            display_name=str(payload.get("name", payload.get("email", ""))),
            role=role,
            site_ids=tuple(int(value) for value in payload.get("sites", [])),
            session_id=str(payload.get("sid")) if payload.get("sid") else None,
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _token_from_request(request: Request) -> str | None:
    authorization = request.headers.get(SESSION_HEADER, "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.cookies.get(settings.session_cookie_name)


def get_identity_optional(request: Request) -> Identity | None:
    token = _token_from_request(request)
    if token:
        return decode_session_token(token)
    if settings.app_environment in {"development", "test"}:
        # Anonymous reads are useful for local API smoke and do not grant any
        # write or action permission.  Site isolation remains enforced when a
        # real identity is supplied.
        return Identity("anonymous", "", "Anonymous", "viewer", (), anonymous=True)
    raise HTTPException(status_code=401, detail="authentication_required")


def get_current_identity(request: Request) -> Identity:
    identity = get_identity_optional(request)
    if identity is None or identity.anonymous:
        raise HTTPException(status_code=401, detail="authentication_required")
    token = _token_from_request(request)
    if token:
        from .auth_repository import session_is_active
        if not session_is_active(identity, token):
            raise HTTPException(status_code=401, detail="session_revoked")
    return identity


def require_roles(*roles: str) -> Callable:
    allowed = set(roles)
    if not allowed.issubset(ROLE_LEVEL):
        raise ValueError(f"Unknown role in dependency: {allowed - set(ROLE_LEVEL)}")

    def dependency(identity: Identity = Depends(get_current_identity)) -> Identity:
        if identity.role not in allowed and not (identity.is_admin and "admin" in allowed):
            raise HTTPException(status_code=403, detail="insufficient_role")
        return identity

    return dependency


def require_site(identity: Identity, site_id: int) -> None:
    if identity.anonymous:
        return
    if not identity.can_access_site(site_id):
        raise HTTPException(status_code=404, detail="resource_not_found")


def set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_s,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
