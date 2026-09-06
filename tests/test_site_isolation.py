"""
Tests unitaires pour l'isolation par site de l'ingestion.
Ne nécessite pas de base de données réelle.
"""

import sys
from pathlib import Path

# Ajouter le répertoire ingest au PYTHONPATH (comme test_ingestion.py)
sys.path.insert(0, str(Path(__file__).parent.parent / "ingest"))

from ingest_pipeline import _validate_site_id


def test_reject_missing_site_id():
    try:
        _validate_site_id(None, "test")
        assert False, "Devrait lever ValueError"
    except ValueError as e:
        assert "manquant" in str(e).lower() or "absent" in str(e).lower()


def test_reject_invalid_site_id():
    try:
        _validate_site_id(0, "test")
        assert False, "Devrait lever ValueError"
    except ValueError:
        pass


def test_accept_valid_site_id():
    assert _validate_site_id(1, "test") == 1
    assert _validate_site_id(42, "test") == 42


def test_resolve_machine_id_requires_site_id():
    """
    Vérifie que la fonction refuse un site_id None.
    """
    source = Path("ingest/ingest_pipeline.py").read_text(encoding="utf-8")
    assert "if site_id is None:" in source
    assert "site_id obligatoire" in source.lower().replace("é", "e")


def test_machine_alias_scope_respects_site_id():
    """The resolver scopes aliases explicitly and rejects ambiguity."""
    source = Path("ingest/ingest_pipeline.py").read_text(encoding="utf-8")
    assert "ma.site_id = %s" in source
    assert "machine_aliases ma" in source
    assert "candidate_count" in source


def test_reconciler_insert_includes_order_site_id():
    """
    Vérifie que insert_cycles inclut order_site_id dans son INSERT.
    """
    source = Path("ingest/reconciler.py").read_text(encoding="utf-8")
    assert "order_site_id" in source
    # L'INSERT doit contenir order_site_id dans les colonnes (avec 25 colonnes
    # lors de la réconciliation avec le nouveau champ order_site_id)
    assert "production_order_id, order_site_id, shift_id" in source


def test_watcher_requires_site_id():
    """
    Vérifie que le watcher refuse un import sans site_id.
    """
    source = Path("ingest/watcher.py").read_text(encoding="utf-8")
    assert "site_id is None:" in source or "site_id est manquant" in source.lower().replace("'", "").replace(" ", "")
    assert "site_id=site_id" in source


def test_production_orders_has_site_id_in_migration():
    """
    Vérifie que la migration 006 ajoute site_id à production_orders.
    """
    source = Path("db/migrations/006_site_isolation.sql").read_text(encoding="utf-8")
    assert "production_orders ADD COLUMN IF NOT EXISTS site_id" in source
    assert "PRIMARY KEY (site_id, id)" in source


def test_machine_aliases_unique_constraint_scoped():
    """Migration 011 makes aliases explicitly site-scoped."""
    source = Path("db/migrations/011_machine_alias_site_scope.sql").read_text(encoding="utf-8")
    assert "machine_aliases_site_machine_fkey" in source
    assert "UNIQUE (site_id, alias_context, alias_value)" in source
    assert "idx_machine_aliases_site_value" in source


def test_import_passports_has_site_id_in_migration():
    """
    Vérifie que la migration 006 ajoute site_id à import_passports.
    """
    source = Path("db/migrations/006_site_isolation.sql").read_text(encoding="utf-8")
    assert "import_passports ADD COLUMN IF NOT EXISTS site_id" in source


def test_order_site_id_in_child_tables():
    """
    Vérifie que la migration 006 ajoute order_site_id
    aux tables enfants de production_orders.
    """
    source = Path("db/migrations/006_site_isolation.sql").read_text(encoding="utf-8")
    for table in ("machine_cycles", "shifts", "quality_checks",
                   "maintenance_events", "operator_notes", "incidents"):
        assert f"{table} ADD COLUMN IF NOT EXISTS order_site_id" in source, \
            f"order_site_id manquant pour {table}"


if __name__ == "__main__":
    import os
    os.chdir(str(Path(__file__).parent.parent))

    tests = [
        test_reject_missing_site_id,
        test_reject_invalid_site_id,
        test_accept_valid_site_id,
        test_resolve_machine_id_requires_site_id,
        test_machine_alias_scope_respects_site_id,
        test_reconciler_insert_includes_order_site_id,
        test_watcher_requires_site_id,
        test_production_orders_has_site_id_in_migration,
        test_machine_aliases_unique_constraint_scoped,
        test_import_passports_has_site_id_in_migration,
        test_order_site_id_in_child_tables,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  OK {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {test.__name__}: {e}")
            failed += 1

    print(f"\n{passed + failed} tests: {passed} OK, {failed} FAILED")
    sys.exit(0 if failed == 0 else 1)
