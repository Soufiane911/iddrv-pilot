import inspect
from pathlib import Path

from ingest.ingest_pipeline import ingest_erp_file


def test_erp_retry_never_deletes_existing_business_orders():
    source = inspect.getsource(ingest_erp_file)
    assert "DELETE FROM production_orders" not in source
    assert "DELETE FROM shifts" not in source
    assert source.index("SET status='completed'") < source.index("conn.commit()")


def test_decided_action_proposal_is_immutable():
    source = Path("backend/app/repositories.py").read_text(encoding="utf-8")
    assert "WHERE action_proposals.status='proposed'" in source
    route = Path("backend/app/api/actions.py").read_text(encoding="utf-8")
    assert "action_already_decided" in route
    assert "ON CONFLICT (proposal_id) DO NOTHING" in source


def test_admin_explicit_site_does_not_inherit_site_one():
    source = Path("scripts/create_admin.py").read_text(encoding="utf-8")
    assert 'action="append", default=None' in source
    assert "site_ids = args.site_id or [1]" in source
    assert "DELETE FROM sessions WHERE user_id=%s" in source
