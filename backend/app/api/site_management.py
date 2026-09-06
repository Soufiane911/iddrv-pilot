from fastapi import APIRouter, Depends, HTTPException, Response

from ..auth_repository import replace_session_token
from ..schemas import SiteCreateInput
from ..security import Identity, create_session_token, require_roles, set_session_cookie
from ..site_repository import SiteConflict, SiteNotFound, archive_site, create_site, delete_site


router = APIRouter(prefix="/api/v1/sites", tags=["site-management"])


def _refresh_session(identity: Identity, response: Response, *, site_id: int | None = None) -> None:
    roles = dict(identity.site_roles)
    if site_id is not None:
        roles[site_id] = identity.role
    refreshed = Identity(
        identity.user_id,
        identity.email,
        identity.display_name,
        identity.role,
        tuple(sorted(roles)),
        identity.session_id,
        site_roles=tuple(sorted(roles.items())),
    )
    token, expires_at = create_session_token(refreshed)
    if identity.session_id and replace_session_token(identity.session_id, token, expires_at):
        set_session_cookie(response, token)


@router.post("", status_code=201)
def provision_site(payload: SiteCreateInput, response: Response, identity: Identity = Depends(require_roles("supervisor", "admin"))):
    try:
        created = create_site(
            name=payload.name,
            timezone=payload.timezone,
            creator_id=identity.user_id,
            creator_role=identity.role,
        )
        _refresh_session(identity, response, site_id=int(created["id"]))
        return created
    except SiteConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _archive_response(site_id: int, response: Response, identity: Identity) -> Response:
    # Archived sites are removed from the current session scope, while the
    # database keeps the site role and all historical data intact.
    if site_id in identity.site_ids:
        roles = tuple((value, role) for value, role in identity.site_roles if value != site_id)
        refreshed = Identity(
            identity.user_id, identity.email, identity.display_name, identity.role,
            tuple(value for value, _ in roles), identity.session_id, site_roles=roles,
        )
        token, expires_at = create_session_token(refreshed)
        if identity.session_id and replace_session_token(identity.session_id, token, expires_at):
            set_session_cookie(response, token)
    response.status_code = 204
    return response


@router.post("/{site_id}/archive", status_code=204)
def archive(site_id: int, response: Response, identity: Identity = Depends(require_roles("admin"))):
    """Archive a site without deleting its presses or history."""
    try:
        archive_site(site_id)
    except SiteNotFound:
        raise HTTPException(status_code=404, detail="site_not_found") from None
    except SiteConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return _archive_response(site_id, response, identity)


@router.delete("/{site_id}", status_code=204)
def remove_site(site_id: int, response: Response, identity: Identity = Depends(require_roles("admin"))):
    """Legacy route retained for clients; it now performs an archive only."""
    try:
        delete_site(site_id)
    except SiteNotFound:
        raise HTTPException(status_code=404, detail="site_not_found") from None
    except SiteConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return _archive_response(site_id, response, identity)
