from fastapi import APIRouter, Depends, HTTPException
from ..security import Identity, get_current_identity, require_site, require_site_roles
from ..connection_repository import local_machine
from ..hdt_control_repository import get_control, set_control

router = APIRouter(prefix='/api/v1/machines', tags=['hdt-control'])

def machine_or_404(machine_id, identity, write=False):
    machine = local_machine(machine_id)
    if not machine:
        raise HTTPException(404, 'machine_not_found')
    if machine.get('site_lifecycle_status') == 'archived' or machine.get('machine_lifecycle_status') == 'archived':
        raise HTTPException(409, 'machine_archived')
    if write:
        require_site_roles(identity, machine['site_id'], 'supervisor', 'admin')
    else:
        require_site(identity, machine['site_id'])
    return machine

@router.get('/{machine_id}/hdt-control')
def read(machine_id: int, identity: Identity = Depends(get_current_identity)):
    machine_or_404(machine_id, identity)
    return get_control(machine_id)

@router.post('/{machine_id}/hdt-control/activate')
def activate(machine_id: int, identity: Identity = Depends(get_current_identity)):
    machine = machine_or_404(machine_id, identity, True)
    return set_control(machine, 'active', identity.user_id)

@router.post('/{machine_id}/hdt-control/stop')
def stop(machine_id: int, identity: Identity = Depends(get_current_identity)):
    machine = machine_or_404(machine_id, identity, True)
    return set_control(machine, 'stopped', identity.user_id)
