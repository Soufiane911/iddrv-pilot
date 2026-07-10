from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..auth_repository import authenticate, create_user, replace_session_token, revoke_session, save_session
from ..schemas import AuthUser, CreateUserRequest, LoginRequest, LoginResponse
from ..security import (
    Identity,
    clear_session_cookie,
    create_session_token,
    get_current_identity,
    require_roles,
    set_session_cookie,
)


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _user(identity: Identity):
    return {"id": identity.user_id, "email": identity.email, "display_name": identity.display_name,
            "role": identity.role, "site_ids": list(identity.site_ids)}


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response):
    identity = authenticate(payload.email, payload.password)
    if identity is None:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token, expires_at = create_session_token(identity)
    session_id = save_session(identity, token, expires_at)
    if session_id:
        identity = Identity(identity.user_id, identity.email, identity.display_name, identity.role, identity.site_ids, session_id)
        token, expires_at = create_session_token(identity, expires_at=expires_at)
        # Persist the hash of the token that is actually sent to the client.
        replace_session_token(session_id, token, expires_at)
    set_session_cookie(response, token)
    return {"user": _user(identity), "expires_at": expires_at}


@router.post("/users", response_model=AuthUser, status_code=201)
def users(payload: CreateUserRequest, identity: Identity = Depends(require_roles("admin"))):
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
    token = request.cookies.get("iddrv_session") or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token:
        revoke_session(token)
    clear_session_cookie(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=AuthUser)
def me(identity: Identity = Depends(get_current_identity)):
    return _user(identity)
