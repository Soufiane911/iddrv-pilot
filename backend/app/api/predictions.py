from datetime import datetime
from fastapi import APIRouter, Depends, Query
from ..prediction_repository import prediction_history
from ..security import Identity, get_current_identity
from .machine_connections import authorized_machine
from .production_context import time_bounds

router = APIRouter(prefix='/api/v1/machines',tags=['predictions'])

@router.get('/{machine_id}/hdt-predictions')
def read(machine_id:int, from_:datetime|None=Query(None,alias='from'),to:datetime|None=None,
         known_at:datetime|None=None,limit:int=Query(500,ge=1,le=5000),identity:Identity=Depends(get_current_identity)):
    machine = authorized_machine(machine_id,identity)
    start,end,known = time_bounds(from_,to,known_at)
    return prediction_history(site_id=machine['site_id'],machine_id=machine_id,start=start,end=end,known_at=known,limit=limit)
