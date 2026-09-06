from fastapi import APIRouter, Depends, HTTPException
from ingest.erp_repository import ERPConflict
from ..erp_import_repository import get_calendar, save_calendar
from ..schemas import ShiftCalendarInput
from ..security import Identity, get_current_identity, require_site, require_site_roles

router = APIRouter(prefix='/api/v1/sites', tags=['shift-calendars'])


@router.get('/{site_id}/shift-calendar')
def read_calendar(site_id: int, identity: Identity = Depends(get_current_identity)):
    require_site(identity, site_id)
    return get_calendar(site_id)


@router.put('/{site_id}/shift-calendar')
def put_calendar(site_id: int, payload: ShiftCalendarInput, identity: Identity = Depends(get_current_identity)):
    require_site_roles(identity, site_id, 'supervisor', 'admin')
    try:
        return save_calendar(site_id=site_id, author_id=identity.user_id, payload=payload.model_dump(mode='json'))
    except ERPConflict as error:
        raise HTTPException(409, str(error)) from None
