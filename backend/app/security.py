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
import binascii
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
    site_roles: tuple[tuple[int, str], ...] = ()

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def can_access_site(self, site_id: int) -> bool:
        return self.anonymous or site_id in self.site_ids

    def role_for_site(self, site_id: int) -> str | None:
        if self.anonymous:
            return "viewer"
        if self.site_roles:
            return dict(self.site_roles).get(site_id)
        return self.role if site_id in self.site_ids else None


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
        "site_roles": {str(site_id): role for site_id, role in identity.site_roles},
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
        session_id = payload.get("sid")
        if not isinstance(session_id, str) or not session_id.strip():
            return None
        site_ids = tuple(int(value) for value in payload.get("sites", []))
        raw_site_roles = payload.get("site_roles", {})
        if not isinstance(raw_site_roles, dict):
            return None
        site_roles = tuple(
            sorted((int(site_id), str(site_role)) for site_id, site_role in raw_site_roles.items())
        )
        if any(site_role not in ROLE_LEVEL or site_id not in site_ids for site_id, site_role in site_roles):
            return None
        if not site_roles:
            site_roles = tuple((site_id, role) for site_id in site_ids)
        return Identity(
            user_id=str(payload["sub"]),
            email=str(payload.get("email", "")),
            display_name=str(payload.get("name", payload.get("email", ""))),
            role=role,
            site_ids=site_ids,
            session_id=session_id,
            site_roles=site_roles,
        )
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _token_from_request(request: Request) -> str | None:
    authorization = request.headers.get(SESSION_HEADER, "")
    if authorization:
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="invalid_token")
        token = authorization[7:].strip()
        if not token:
            raise HTTPException(status_code=401, detail="invalid_token")
        return token
    return request.cookies.get(settings.session_cookie_name)


def get_identity_optional(request: Request) -> Identity | None:
    token = _token_from_request(request)
    if token:
        identity = decode_session_token(token)
        if identity is None:
            raise HTTPException(status_code=401, detail="invalid_token")
        from .auth_repository import session_is_active
        if not session_is_active(identity, token):
            raise HTTPException(status_code=401, detail="session_revoked")
        return identity
    if settings.allow_anonymous_reads:
        # Anonymous reads are an explicit local-only opt-in.
        return Identity("anonymous", "", "Anonymous", "viewer", (), anonymous=True)
    raise HTTPException(status_code=401, detail="authentication_required")


def get_current_identity(request: Request) -> Identity:
    identity = get_identity_optional(request)
    if identity is None or identity.anonymous:
        raise HTTPException(status_code=401, detail="authentication_required")
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


def require_site_roles(identity: Identity, site_id: int, *roles: str) -> None:
    require_site(identity, site_id)
    if identity.role_for_site(site_id) not in set(roles):
        raise HTTPException(status_code=403, detail="insufficient_role")


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
