from datetime import datetime, timedelta, timezone

from backend.app.diagnostics.runtime import detect_scrap_windows


def _row(index: int, scrap: bool):
    return {
        "time": datetime(2026, 7, 10, tzinfo=timezone.utc) + timedelta(seconds=index),
        "machine_id": 7,
        "production_order_id": "OF-1",
        "scrap_flag": scrap,
        "part_quality_status": "scrap" if scrap else "good",
        "defect_type": "short_shot" if scrap else None,
    }


def test_detector_requires_thirty_incident_and_baseline_cycles():
    assert detect_scrap_windows([_row(i, i >= 29) for i in range(59)]) == []


def test_detector_finds_scrap_increase_without_scenario_identifier():
    rows = [_row(i, False) for i in range(30)] + [_row(i + 30, i < 20) for i in range(30)]
    windows = detect_scrap_windows(rows)
    assert len(windows) == 1
    assert windows[0].baseline_rate == 0
    assert windows[0].incident_rate > 0.6
    assert windows[0].defect_type == "short_shot"


def test_detector_does_not_flag_healthy_window():
    rows = [_row(i, i % 25 == 0) for i in range(90)]
    assert detect_scrap_windows(rows) == []


def test_unknown_cycle_quality_never_becomes_a_zero_scrap_rate():
    from backend.app.diagnostics.engine import observed_scrap_rate
    assert observed_scrap_rate([{'scrap_flag':None},{'quality_flag':'valid'}])==(None,0)
    assert observed_scrap_rate([{'scrap_flag':None},{'scrap_flag':False},{'scrap_flag':True}])==(.5,2)


def test_process_drift_investigation_abstains_without_quality_observations(monkeypatch):
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.security import Identity,create_session_token
    from backend.app.api import incidents
    at=datetime(2026,9,5,tzinfo=timezone.utc)
    incident={'site_id':1,'machine_id':7,'origin':'process_drift','started_at':at,'data_cutoff':at+timedelta(hours=1)}
    monkeypatch.setattr(incidents,'get_incident',lambda *a,**kw:incident)
    class Repository:
        def __init__(self,**kwargs): pass
        def quality_checks(self,*args): return []
    monkeypatch.setattr('backend.app.diagnostics.postgres.PostgresDiagnosticRepository',Repository)
    token,_=create_session_token(Identity('u','test@example.test','Test','analyst',(1,)))
    result=TestClient(app).post(f'/api/v1/incidents/{uuid4()}/investigations',headers={'Authorization':'Bearer '+token})
    assert result.status_code==422
    assert result.json()['error']['message']=='process_drift_quality_observations_required'
