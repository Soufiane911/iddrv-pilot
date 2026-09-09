"""Authenticated, site-scoped, bounded replay with no persistence side effects."""
import time
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from ..security import Identity, require_roles, require_site
from ..services import summary6 as service
from ml.runtime_mode import runtime_mode
from ..services.summary6_admission import admit

router = APIRouter(prefix='/api/v1/process-drift/summary6', tags=['machine-learning'])
auth = require_roles('viewer', 'analyst', 'supervisor', 'admin')


def authorize_site(identity, site_id):
    try:
        require_site(identity, site_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(403, 'site_access_denied') from None
        raise


class DemoSource(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Literal['demo_dataset']
    dataset_id: str = Field(min_length=1, max_length=80)
    lot_id: str = Field(min_length=1, max_length=40)
    through_cycle: int = Field(ge=0, le=399)


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    site_id: int = Field(gt=0, le=9223372036854775807)
    expected_package_id: str = Field(min_length=1, max_length=100)
    source: Annotated[DemoSource, Field(discriminator='kind')]


@router.get('/current')
def current(identity: Identity = Depends(auth)):
    with admit(identity):
        return service.current()


@router.get('/demo-datasets')
def datasets(site_id: int = Query(gt=0, le=9223372036854775807), identity: Identity = Depends(auth)):
    authorize_site(identity, site_id)
    try:
        return service.catalog()
    except service.Unavailable as exc:
        raise HTTPException(503, str(exc)) from None


@router.post('/replay')
def replay(payload: ReplayRequest, identity: Identity = Depends(auth)):
    authorize_site(identity, payload.site_id)
    if runtime_mode() != 'summary6_replay':
        raise HTTPException(409, 'summary6_profile_not_enabled')
    with admit(identity):
        return admitted_replay(payload)


def admitted_replay(payload):
    started = time.perf_counter()
    try:
        loaded = service.package()
        if payload.expected_package_id != loaded.runtime_id:
            raise HTTPException(409, 'summary6_package_identity_changed')
        result = service.replay(payload.source, loaded)
        from ..metrics import record_summary6
        record_summary6(result['latest'], time.perf_counter() - started)
        return dict(site_id=payload.site_id, **result)
    except service.Unavailable as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
