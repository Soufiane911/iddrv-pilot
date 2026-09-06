from fastapi import APIRouter, Depends, HTTPException
from ..erp_import_repository import create_machine
from ..schemas import MachineCreateInput
from ..security import Identity, get_current_identity, require_site_roles

router = APIRouter(prefix='/api/v1/sites', tags=['topology'])


@router.post('/{site_id}/machines', status_code=201)
def add_machine(site_id: int, payload: MachineCreateInput, identity: Identity = Depends(get_current_identity)):
    require_site_roles(identity, site_id, 'supervisor', 'admin')
    machine = create_machine(site_id=site_id, **payload.model_dump())
    if machine is None:
        raise HTTPException(409, 'machine_ref_already_exists')
    return machine
