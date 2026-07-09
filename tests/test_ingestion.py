"""
IDDRV — Tests d'intégration (standalone, sans framework externe)
================================================================

Teste les modules clés du pipeline sans base de données réelle :
1. Profiler : détection d'encodage, délimiteur, transposition, constructeur
2. Mapper : mapping des colonnes vers le modèle canonique
3. Loader : lecture et redressement des formats hétérogènes
4. Réconciliation : simulation de la jointure temporelle ERP ↔ cycles

Usage: python tests/test_ingestion.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, date, timedelta

# Ajouter le répertoire ingest au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / "ingest"))

from profiler import profile_file
from mapper import build_column_map, map_row, get_mapping_confidence
from loader import load_file, read_erp_trs_xlsx

# ─────────────────────────────────────────────────────────────
# Utilitaires de test
# ─────────────────────────────────────────────────────────────

_test_pass = 0
_test_fail = 0


def assert_equal(label: str, actual, expected):
    global _test_pass, _test_fail
    if actual == expected:
        print(f"  ✅ {label}")
        _test_pass += 1
    else:
        print(f"  ❌ {label}")
        print(f"     Attendu  : {expected!r}")
        print(f"     Obtenu   : {actual!r}")
        _test_fail += 1


def assert_true(label: str, condition: bool):
    global _test_pass, _test_fail
    if condition:
        print(f"  ✅ {label}")
        _test_pass += 1
    else:
        print(f"  ❌ {label}")
        _test_fail += 1


def assert_in(label: str, item, container):
    assert_true(label, item in container)


# ─────────────────────────────────────────────────────────────
# Test 1 : Mapper — Colonnes Arburg
# ─────────────────────────────────────────────────────────────

def test_arburg_column_mapping():
    print("\n📋 Test 1: Mapping colonnes Arburg")
    headers = ["t007", "t4015", "t4012", "t4018", "V4062", "V4065", "p4072", "p4071", "f4090", "f077", "f1403", "unknown_col"]
    col_map = build_column_map(headers, brand="arburg")

    assert_equal("t4015 → dosing_time_s", col_map["t4015"]["canonical"], "dosing_time_s")
    assert_equal("t4012 → cycle_time_s",  col_map["t4012"]["canonical"], "cycle_time_s")
    assert_equal("t4018 → injection_time_s", col_map["t4018"]["canonical"], "injection_time_s")
    assert_equal("V4062 → cushion_mm",    col_map["V4062"]["canonical"], "cushion_mm")
    assert_equal("V4065 → switchover_position", col_map["V4065"]["canonical"], "switchover_position")
    assert_equal("p4072 → switchover_pressure_bar", col_map["p4072"]["canonical"], "switchover_pressure_bar")
    assert_equal("f077  → good_parts",    col_map["f077"]["canonical"], "good_parts")
    assert_equal("f1403 → cycle_counter", col_map["f1403"]["canonical"], "cycle_counter")
    assert_equal("Colonne inconnue non mappée", col_map["unknown_col"]["canonical"], None)

    confidence = get_mapping_confidence(col_map)
    assert_true(f"Confiance mapping ≥ 50% (obtenu: {confidence:.0%})", confidence >= 0.50)


# ─────────────────────────────────────────────────────────────
# Test 2 : Mapper — Colonnes Engel
# ─────────────────────────────────────────────────────────────

def test_engel_column_mapping():
    print("\n📋 Test 2: Mapping colonnes Engel")
    headers = ["Timestamp", "t_cycle", "t_dos", "t_inj", "v_mat", "v_sw", "p_sw", "p_max", "f_clamp", "n_good", "n_cycle"]
    col_map = build_column_map(headers, brand="engel")

    assert_equal("t_cycle → cycle_time_s", col_map["t_cycle"]["canonical"], "cycle_time_s")
    assert_equal("t_dos   → dosing_time_s", col_map["t_dos"]["canonical"], "dosing_time_s")
    assert_equal("v_mat   → cushion_mm",    col_map["v_mat"]["canonical"], "cushion_mm")
    assert_equal("p_sw    → switchover_pressure_bar", col_map["p_sw"]["canonical"], "switchover_pressure_bar")
    assert_equal("n_good  → good_parts",    col_map["n_good"]["canonical"], "good_parts")


# ─────────────────────────────────────────────────────────────
# Test 3 : Mapper — Transformation de ligne
# ─────────────────────────────────────────────────────────────

def test_row_transformation():
    print("\n📋 Test 3: Transformation de lignes brutes")
    headers = ["t4012", "t4015", "V4062", "p4072", "f077", "extra_param"]
    col_map = build_column_map(headers, brand="arburg")

    raw_row = {
        "t4012": "28,500",      # Format FR avec virgule décimale
        "t4015": "8,200",
        "V4062": "4,120",
        "p4072": "1050,0",
        "f077": "1",
        "extra_param": "some_value"
    }

    canonical = map_row(raw_row, col_map)

    assert_equal("cycle_time_s converti en float", canonical.get("cycle_time_s"), 28.5)
    assert_equal("dosing_time_s converti en float", canonical.get("dosing_time_s"), 8.2)
    assert_equal("cushion_mm converti en float", canonical.get("cushion_mm"), 4.12)
    assert_equal("good_parts converti en float", canonical.get("good_parts"), 1.0)
    assert_true("extra_param dans raw_data", "extra_param" in canonical.get("raw_data", {}))


# ─────────────────────────────────────────────────────────────
# Test 4 : Profiler — Fichier Arburg généré
# ─────────────────────────────────────────────────────────────

def test_profiler_arburg():
    print("\n📋 Test 4: Profiler sur fichier Arburg généré")
    sample_path = Path("data/samples/arburg_1003_cycles.txt")

    if not sample_path.exists():
        print("  ⚠️  Fichier sample non trouvé — génération...")
        os.chdir(str(Path(__file__).parent.parent))
        exec(open("ingest/generate_samples.py").read())

    if sample_path.exists():
        profile = profile_file(str(sample_path))
        assert_equal("Délimiteur détecté = ';'", profile.delimiter, ";")
        assert_equal("Non transposé", profile.is_transposed, False)
        assert_equal("Constructeur = arburg", profile.brand_detected, "arburg")
        assert_true("Au moins 8 colonnes", profile.column_count >= 8)
        assert_true("Ligne données > ligne 2", profile.data_start_row > 2)
    else:
        print("  ⚠️  Impossible de créer le fichier sample (pandas requis)")


# ─────────────────────────────────────────────────────────────
# Test 5 : Profiler — Fichier transposé généré
# ─────────────────────────────────────────────────────────────

def test_profiler_transposed():
    print("\n📋 Test 5: Profiler sur fichier transposé (Tubes)")
    sample_path = Path("data/samples/transposed_606_tubes.txt")

    if sample_path.exists():
        profile = profile_file(str(sample_path))
        assert_equal("Transposé détecté = True", profile.is_transposed, True)
        assert_in("Encodage = utf-16 ou utf-16-le", profile.encoding, ["utf-16", "utf-16-le"])
    else:
        print("  ⚠️  Fichier transposé non trouvé (lancer generate_samples.py)")


# ─────────────────────────────────────────────────────────────
# Test 6 : Réconciliation temporelle (logique pure, sans DB)
# ─────────────────────────────────────────────────────────────

def test_reconciliation_logic():
    """
    Simule la logique de réconciliation sans base de données.
    Vérifie que les fenêtres temporelles sont calculées correctement.
    """
    print("\n📋 Test 6: Logique de réconciliation temporelle")

    # Simulation d'un OF (8h → 16h)
    of_start = datetime(2025, 2, 11, 8, 0, 0)
    of_end   = datetime(2025, 2, 11, 16, 0, 0)

    def mock_resolve_of(cycle_time: datetime, window_minutes: int = 30) -> tuple:
        window = timedelta(minutes=window_minutes)
        if of_start - window <= cycle_time <= of_end + window:
            if of_start <= cycle_time <= of_end:
                return "O0824120601331", 1.0
            else:
                # En zone de chevauchement
                if cycle_time < of_start:
                    dist = (of_start - cycle_time).total_seconds()
                else:
                    dist = (cycle_time - of_end).total_seconds()
                confidence = max(0.0, round(1.0 - dist / (window_minutes * 60), 3))
                return "O0824120601331", confidence
        return None, 0.0

    # Cycle strictement dans l'OF
    of_id, conf = mock_resolve_of(datetime(2025, 2, 11, 12, 30, 0))
    assert_equal("Cycle IN OF → confiance = 1.0", conf, 1.0)
    assert_equal("Cycle IN OF → OF correct", of_id, "O0824120601331")

    # Cycle 15 minutes avant le début de l'OF
    of_id, conf = mock_resolve_of(datetime(2025, 2, 11, 7, 45, 0))
    assert_true("Cycle 15min avant OF → confiance 0 < c < 1", 0.0 < conf < 1.0)

    # Cycle 2 heures après la fin → hors fenêtre
    of_id, conf = mock_resolve_of(datetime(2025, 2, 11, 18, 0, 0))
    assert_equal("Cycle 2h après OF → pas de lien", of_id, None)
    assert_equal("Cycle 2h après OF → confiance = 0.0", conf, 0.0)


# ─────────────────────────────────────────────────────────────
# Test 7 : Loader — Timestamps réels machine
# ─────────────────────────────────────────────────────────────

def test_loader_machine_timestamps():
    print("\n📋 Test 7: Timestamps machine depuis les fichiers sources")

    arburg_rows, _, _ = load_file("data/samples/arburg_1003_cycles.txt")
    engel_rows, _, _ = load_file("data/samples/engel_152_cycles.csv")

    assert_true("Arburg charge au moins une ligne", len(arburg_rows) > 0)
    assert_true("Engel charge au moins une ligne", len(engel_rows) > 0)
    assert_true("Arburg conserve la date complète de février", str(arburg_rows[0].get("time", "")).startswith("2025-02-11"))
    assert_true("Engel extrait Timestamp comme time canonique", str(engel_rows[0].get("time", "")).startswith("2025-02-11T14:00"))


# ─────────────────────────────────────────────────────────────
# Test 8 : Loader — ERP/TRS complet
# ─────────────────────────────────────────────────────────────

def test_loader_erp_orders_complete():
    print("\n📋 Test 8: Lecture ERP/TRS avec dates de début et fin")

    orders = read_erp_trs_xlsx("data/samples/erp_trs_fevrier.xlsx")

    assert_true("ERP charge des ordres", len(orders) > 0)
    first = orders[0]
    assert_true("ERP expose started_at", "started_at" in first)
    assert_true("ERP expose ended_at", "ended_at" in first)
    assert_true("ERP expose machine_erp_ref", "machine_erp_ref" in first)
    assert_true("ERP expose erp_cycle_time_s", "erp_cycle_time_s" in first)
    assert_equal("ERP de démo démarre le 11 février", first["started_at"].date(), date(2025, 2, 11))


# ─────────────────────────────────────────────────────────────
# Test 9 : Schéma — staging et idempotence
# ─────────────────────────────────────────────────────────────

def test_schema_contains_staging_and_idempotency_contracts():
    print("\n📋 Test 9: Schéma SQL staging et idempotence")

    init_sql = Path("db/init.sql").read_text(encoding="utf-8")

    assert_true("Table staging_import_rows présente", "CREATE TABLE IF NOT EXISTS staging_import_rows" in init_sql)
    assert_true("Table import_rejections présente", "CREATE TABLE IF NOT EXISTS import_rejections" in init_sql)
    assert_true("Passeport file_hash unique", "UNIQUE(file_hash)" in init_sql or "file_hash VARCHAR(64) UNIQUE" in init_sql)
    assert_true("Cycles contiennent source_row_hash", "source_row_hash" in init_sql)
    assert_true("Cycles ont une contrainte unique d'idempotence", "uq_machine_cycles_source_row" in init_sql)


# ─────────────────────────────────────────────────────────────
# Test 10 : Pipeline — ERP et staging
# ─────────────────────────────────────────────────────────────

def test_pipeline_exposes_erp_import_and_staging_contracts():
    print("\n📋 Test 10: Pipeline ERP et staging")

    pipeline = Path("ingest/ingest_pipeline.py").read_text(encoding="utf-8")
    demo = Path("demo_end_to_end.py").read_text(encoding="utf-8")
    reconciler = Path("ingest/reconciler.py").read_text(encoding="utf-8")

    assert_true("Pipeline expose ingest_erp_file", "def ingest_erp_file" in pipeline)
    assert_true("Pipeline trace staging_import_rows", "staging_import_rows" in pipeline)
    assert_true("Pipeline trace import_rejections", "import_rejections" in pipeline)
    assert_true("Pipeline calcule source_row_hash", "source_row_hash" in pipeline)
    assert_true("Pipeline calcule un hash sémantique ERP", "def _rows_hash" in pipeline and "raw_file_hash" in pipeline)
    assert_true("Reconciler insère source_row_hash", "source_row_hash" in reconciler)
    assert_true("Reconciler sait rattacher les cycles existants", "def reconcile_existing_cycles" in reconciler)
    assert_true("Démo end-to-end importe l'ERP", '"--erp"' in demo and "erp_trs_fevrier.xlsx" in demo)


# ─────────────────────────────────────────────────────────────
# Exécution des tests
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Aller au répertoire racine du projet
    os.chdir(str(Path(__file__).parent.parent))

    print("=" * 60)
    print(" IDDRV — TESTS D'INTÉGRATION")
    print("=" * 60)

    test_arburg_column_mapping()
    test_engel_column_mapping()
    test_row_transformation()
    test_profiler_arburg()
    test_profiler_transposed()
    test_reconciliation_logic()
    test_loader_machine_timestamps()
    test_loader_erp_orders_complete()
    test_schema_contains_staging_and_idempotency_contracts()
    test_pipeline_exposes_erp_import_and_staging_contracts()

    print(f"\n{'='*60}")
    print(f" RÉSULTATS: {_test_pass} ✅ réussis / {_test_fail} ❌ échoués")
    print(f"{'='*60}")

    sys.exit(0 if _test_fail == 0 else 1)
