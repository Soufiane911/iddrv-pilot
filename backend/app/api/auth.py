from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..auth_repository import (
    AuthenticationUnavailable,
    authenticate,
    create_user,
    replace_session_token,
    revoke_session,
    save_session,
)
from .. import login_throttle
from ..config import settings
from ..schemas import AuthUser, CreateUserRequest, LoginRequest, LoginResponse
from ..security import (
    Identity,
    clear_session_cookie,
    create_session_token,
    get_current_identity,
    require_roles,
    require_site_roles,
    set_session_cookie,
)


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _user(identity: Identity):
    return {
        "id": identity.user_id,
        "email": identity.email,
        "display_name": identity.display_name,
        "role": identity.role,
        "site_ids": list(identity.site_ids),
        "site_roles": {site_id: role for site_id, role in identity.site_roles},
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response):
    origin = login_throttle.client_ip(request)
    try:
        allowed, retry_after = login_throttle.allowed(payload.email, origin)
    except login_throttle.ThrottleUnavailable:
        raise HTTPException(status_code=503, detail="login_throttle_unavailable") from None
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="login_rate_limited",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        identity = authenticate(payload.email, payload.password)
    except AuthenticationUnavailable:
        # Do not count a storage outage as a bad password or retain a slot
        # until its TTL when authentication never reached a result.
        try:
            login_throttle.release_reservation(payload.email, origin)
        except login_throttle.ThrottleUnavailable:
            pass
        raise HTTPException(status_code=503, detail="authentication_unavailable") from None
    if identity is None:
        try:
            login_throttle.record_failure(payload.email, origin)
        except login_throttle.ThrottleUnavailable:
            raise HTTPException(status_code=503, detail="login_throttle_unavailable") from None
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token, expires_at = create_session_token(identity)
    provisional_token = token
    session_id = save_session(identity, token, expires_at)
    if not session_id:
        try:
            login_throttle.release_reservation(payload.email, origin)
        except login_throttle.ThrottleUnavailable:
            pass
        raise HTTPException(status_code=503, detail="session_persistence_unavailable")
    identity = Identity(
        identity.user_id, identity.email, identity.display_name, identity.role,
        identity.site_ids, session_id, site_roles=identity.site_roles,
    )
    token, expires_at = create_session_token(identity, expires_at=expires_at)
    # Persist the hash of the token that is actually sent to the client.
    if not replace_session_token(session_id, token, expires_at):
        revoke_session(provisional_token)
        try:
            login_throttle.release_reservation(payload.email, origin)
        except login_throttle.ThrottleUnavailable:
            pass
        raise HTTPException(status_code=503, detail="session_persistence_unavailable")
    try:
        # Only this identity quota is cleared. The shared origin quota is never
        # reset by a valid account (important for password spraying/NATs).
        login_throttle.clear_failure(payload.email, origin)
    except login_throttle.ThrottleUnavailable:
        raise HTTPException(status_code=503, detail="login_throttle_unavailable") from None
    set_session_cookie(response, token)
    return {"user": _user(identity), "expires_at": expires_at}


@router.post("/users", response_model=AuthUser, status_code=201)
def users(payload: CreateUserRequest, identity: Identity = Depends(require_roles("admin"))):
    if not payload.site_ids:
        raise HTTPException(status_code=422, detail="site_scope_required")
    for site_id in payload.site_ids:
        require_site_roles(identity, site_id, "admin")
    try:
        created = create_user(payload.email, payload.password, payload.display_name, payload.role, payload.site_ids)
    except Exception as exc:
        # Do not expose database details or whether an email already exists.
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="user_already_exists") from None
        raise HTTPException(status_code=422, detail="user_creation_failed") from None
    return _user(created)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response):
    authorization = request.headers.get("Authorization", "")
    bearer = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    token = bearer or request.cookies.get(settings.session_cookie_name)
    if token and not revoke_session(token):
        raise HTTPException(status_code=503, detail="session_revocation_unavailable")
    clear_session_cookie(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=AuthUser)
def me(identity: Identity = Depends(get_current_identity)):
    return _user(identity)
