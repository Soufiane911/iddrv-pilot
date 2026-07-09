"""
Tests de validation du dataset industriel de démonstration.
"""

import json
import os
import pandas as pd
from datetime import datetime, timedelta

BASE = "data/scenarios/industrial_demo"
ORDERS_FILE = f"{BASE}/erp_orders.xlsx"
CYCLES_FILES = {
    "152": f"{BASE}/machine_cycles_152.csv",
    "1003": f"{BASE}/machine_cycles_1003.csv",
    "606": f"{BASE}/machine_cycles_606.csv",
}
QUALITY_FILE = f"{BASE}/quality_checks.csv"
MAINTENANCE_FILE = f"{BASE}/maintenance_events.csv"
NOTES_FILE = f"{BASE}/operator_notes.csv"
GROUND_TRUTH_FILE = f"{BASE}/ground_truth.json"
README_FILE = f"{BASE}/README.md"

VALID_MACHINES = {"152", "1003", "606"}


def _normalize_machine_ref(val):
    """Normalize machine_erp_ref to string for comparison."""
    if isinstance(val, (int, float)):
        return str(int(val))
    return str(val)


def test_01_all_files_exist():
    files = [
        ORDERS_FILE, QUALITY_FILE, MAINTENANCE_FILE,
        NOTES_FILE, GROUND_TRUTH_FILE, README_FILE,
    ] + list(CYCLES_FILES.values())
    for f in files:
        assert os.path.exists(f), f"Fichier manquant: {f}"
    print("OK: Tous les fichiers existent")


def test_02_orders_have_required_columns():
    df = pd.read_excel(ORDERS_FILE)
    required = [
        "production_order_id", "machine_erp_ref", "machine_name",
        "shift_id", "shift_number", "started_at", "ended_at",
        "product_ref", "product_name", "tool_ref", "material_ref",
        "target_quantity", "theoretical_cycle_time_s", "planned_runtime_h",
        "expected_trs", "expected_scrap_rate",
    ]
    for col in required:
        assert col in df.columns, f"Colonne manquante dans ERP: {col}"
    assert len(df) >= 30, f"Trop peu d'ordres: {len(df)} (< 30)"
    machines = {_normalize_machine_ref(v) for v in df["machine_erp_ref"]}
    assert machines == VALID_MACHINES, f"Machines invalides dans ERP: {machines}"
    print(f"OK: {len(df)} ordres avec {len(required)} colonnes obligatoires, machines={sorted(machines)}")


def test_03_cycles_have_valid_order_refs():
    orders_df = pd.read_excel(ORDERS_FILE)
    valid_ids = set(orders_df["production_order_id"])
    for mid, fpath in CYCLES_FILES.items():
        df = pd.read_csv(fpath, parse_dates=["timestamp"])
        assert "production_order_id" in df.columns
        assert "machine_erp_ref" in df.columns
        invalid = set(df["production_order_id"]) - valid_ids
        assert len(invalid) == 0, f"Cycles {mid}: {len(invalid)} OF invalides"
        refs = {_normalize_machine_ref(v) for v in df["machine_erp_ref"]}
        assert set([mid]) == refs, f"Machine {mid} a des refs différentes: {refs}"
        print(f"OK: Cycles {mid}: {len(df)} cycles, tous OF et refs valides")


def test_04_quality_checks_have_valid_order_refs():
    orders_df = pd.read_excel(ORDERS_FILE)
    valid_ids = set(orders_df["production_order_id"])
    df = pd.read_csv(QUALITY_FILE, parse_dates=["timestamp"])
    assert "production_order_id" in df.columns
    invalid = set(df["production_order_id"]) - valid_ids
    assert len(invalid) == 0, f"{len(invalid)} OF invalides dans qualité"
    machines = {_normalize_machine_ref(v) for v in df["machine_erp_ref"]}
    assert machines.issubset(VALID_MACHINES), f"Machines invalides dans qualité: {machines}"
    print(f"OK: {len(df)} contrôles qualité, tous OF et machines valides")


def test_05_maintenance_refs_valid_machine():
    df = pd.read_csv(MAINTENANCE_FILE)
    assert "machine_erp_ref" in df.columns
    machines = {_normalize_machine_ref(v) for v in df["machine_erp_ref"]}
    assert machines.issubset(VALID_MACHINES), f"Machines invalides maintenance: {machines}"
    assert all(df["event_type"] != ""), "Événement maintenance sans type"
    print(f"OK: {len(df)} événements maintenance, machines={sorted(machines)}")


def test_06_ground_truth_has_6_scenarios():
    with open(GROUND_TRUTH_FILE) as f:
        gt = json.load(f)
    assert len(gt) == 6, f"Attendu 6 scénarios, trouvé {len(gt)}"
    ids = {s["scenario_id"] for s in gt}
    expected = {"S001", "S002", "S003", "S004", "S005", "S006"}
    assert ids == expected, f"IDs manquants: {expected - ids}"
    for s in gt:
        assert s.get("root_cause"), f"{s['scenario_id']}: root_cause manquant"
        assert s.get("expected_defect"), f"{s['scenario_id']}: expected_defect manquant"
        assert len(s.get("evidence_fields", [])) >= 2, f"{s['scenario_id']}: evidence_fields insuffisants"
        assert s.get("machine_erp_ref"), f"{s['scenario_id']}: machine_erp_ref manquant"
    print(f"OK: 6 scénarios présents, tous complets")


def test_07_scenarios_have_evidence():
    with open(GROUND_TRUTH_FILE) as f:
        gt = json.load(f)
    orders_df = pd.read_excel(ORDERS_FILE)
    valid_ids = set(orders_df["production_order_id"])
    notes_df = pd.read_csv(NOTES_FILE)
    notes_df["machine_erp_ref"] = notes_df["machine_erp_ref"].apply(_normalize_machine_ref)

    for s in gt:
        mid = s["machine_erp_ref"]
        oid = s["production_order_id"]
        if " to " in oid:
            for p in oid.split(" to "):
                assert p.strip() in valid_ids, f"{s['scenario_id']}: OF {p} introuvable"
        else:
            assert oid in valid_ids, f"{s['scenario_id']}: OF {oid} introuvable"
        cycles_file = CYCLES_FILES[mid]
        cdf = pd.read_csv(cycles_file, parse_dates=["timestamp"])
        assert len(cdf) > 0, f"{s['scenario_id']}: aucun cycle pour {mid}"
        machine_notes = notes_df[notes_df["machine_erp_ref"] == mid]
        assert len(machine_notes) > 0, f"{s['scenario_id']}: aucune note pour {mid}"
        print(f"  OK: {s['scenario_id']} - preuves trouvées (cycles={len(cdf)}, notes={len(machine_notes)})")


def test_08_cycles_within_order_window():
    orders_df = pd.read_excel(ORDERS_FILE)
    order_windows = {}
    for _, row in orders_df.iterrows():
        order_windows[row["production_order_id"]] = (
            pd.to_datetime(row["started_at"]),
            pd.to_datetime(row["ended_at"]),
        )
    total, inside = 0, 0
    for mid, fpath in CYCLES_FILES.items():
        df = pd.read_csv(fpath, parse_dates=["timestamp"])
        for _, row in df.iterrows():
            total += 1
            oid, ts = row["production_order_id"], row["timestamp"]
            if oid in order_windows:
                s, e = order_windows[oid]
                if s <= ts <= e:
                    inside += 1
    pct = inside / total * 100
    assert pct >= 95, f"Seulement {pct:.1f}% dans la fenêtre (attendu >= 95%)"
    print(f"OK: {pct:.1f}% des cycles dans la fenêtre temporelle ({inside}/{total})")


def test_09_at_least_5_defect_types():
    all_flags = set()
    for fpath in CYCLES_FILES.values():
        df = pd.read_csv(fpath)
        all_flags.update(df["quality_flag"].dropna().unique())
    all_flags.discard("good")
    assert len(all_flags) >= 5, f"Seulement {len(all_flags)} types: {all_flags}"
    print(f"OK: {len(all_flags)} types de défauts: {sorted(all_flags)}")


def test_10_imperfect_data_exists():
    found_missing = False
    found_ambiguous = False
    for fpath in CYCLES_FILES.values():
        df = pd.read_csv(fpath)
        if df.isnull().any().any():
            found_missing = True
            break
    notes_df = pd.read_csv(NOTES_FILE)
    ambiguous_kw = ["Cause possible", "intermittents", "pas stable", "a surveiller"]
    for kw in ambiguous_kw:
        if any(kw.lower() in str(n).lower() for n in notes_df.get("note_text", [])):
            found_ambiguous = True
            break
    assert found_missing or found_ambiguous, "Aucune donnée imparfaite"
    print(f"OK: Données imparfaites (manquantes={found_missing}, ambiguës={found_ambiguous})")


def test_11_orders_cover_all_machines():
    df = pd.read_excel(ORDERS_FILE)
    machines = {_normalize_machine_ref(v) for v in df["machine_erp_ref"]}
    assert machines == VALID_MACHINES, f"Machines: {machines}"
    print(f"OK: 3 machines couvertes: {sorted(machines)}")


def test_12_quality_defect_types_match_cycles():
    qdf = pd.read_csv(QUALITY_FILE)
    q_defects = set()
    for dt_str in qdf["defect_type"].dropna():
        for dt in dt_str.split(","):
            dt = dt.strip()
            if dt:
                q_defects.add(dt)
    c_defects = set()
    for fpath in CYCLES_FILES.values():
        df = pd.read_csv(fpath)
        c_defects.update(df["quality_flag"].dropna().unique())
    c_defects.discard("good")
    overlap = q_defects & c_defects
    assert len(overlap) >= 3, f"Trop peu de défauts communs: {overlap}"
    print(f"OK: {len(overlap)} types de défauts communs: {sorted(overlap)}")


def test_13_maintenance_events_have_timestamps():
    df = pd.read_csv(MAINTENANCE_FILE)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    assert df["timestamp"].notna().all(), "Timestamps manquants dans maintenance"
    print("OK: Tous les événements maintenance ont un timestamp valide")


def test_14_scenario_evidence_within_window():
    """Chaque scenario a ses preuves declarees dans la fenetre ±2h."""
    with open(GROUND_TRUTH_FILE) as f:
        gt = json.load(f)
    notes = pd.read_csv(NOTES_FILE)
    notes["timestamp"] = pd.to_datetime(notes["timestamp"])
    maint = pd.read_csv(MAINTENANCE_FILE)
    maint["timestamp"] = pd.to_datetime(maint["timestamp"])

    all_ok = True
    for s in gt:
        sid = s["scenario_id"]
        mid = s["machine_erp_ref"]
        st = datetime.fromisoformat(s["start_time"])
        et = datetime.fromisoformat(s["end_time"])
        win_s = st - timedelta(hours=2)
        win_e = et + timedelta(hours=2)
        ev = s.get("evidence_fields", [])

        if "operator_notes" in ev:
            mask = (notes["machine_erp_ref"].astype(str) == mid) & \
                   (notes["timestamp"] >= win_s) & (notes["timestamp"] <= win_e)
            cnt = len(notes[mask])
            if cnt == 0:
                print(f"  ECHEC {sid}: aucune note operateur dans ±2h ({st} -> {et})")
                all_ok = False

        if "maintenance_events" in ev:
            mask = (maint["machine_erp_ref"].astype(str) == mid) & \
                   (maint["timestamp"] >= win_s) & (maint["timestamp"] <= win_e)
            cnt = len(maint[mask])
            if cnt == 0:
                print(f"  ECHEC {sid}: aucun event maintenance dans ±2h ({st} -> {et})")
                all_ok = False

    assert all_ok, "Certains scenarios n'ont pas leurs preuves dans la fenêtre ±2h"
    print("OK: Chaque scenario a ses preuves (notes/events) dans la fenêtre ±2h")


def test_15_s006_dimensional_drift():
    """S006: dimension_deviation_mm montre une derive croissante nette."""
    with open(GROUND_TRUTH_FILE) as f:
        gt = json.load(f)
    s6 = next(s for s in gt if s["scenario_id"] == "S006")
    orders = pd.read_excel(ORDERS_FILE)
    qc = pd.read_csv(QUALITY_FILE)
    qc["timestamp"] = pd.to_datetime(qc["timestamp"])

    # Find orders on machine 606 using tool A (MOULE-606-A)
    tool_a_oids = set(
        orders[(orders["machine_erp_ref"].astype(str) == "606") &
               (orders["tool_ref"].astype(str).str.contains("A"))]["production_order_id"]
    )
    s6_qc = qc[qc["production_order_id"].isin(tool_a_oids)].sort_values("timestamp")
    assert len(s6_qc) >= 4, f"Pas assez de QC pour S006: {len(s6_qc)}"

    half = len(s6_qc) // 2
    first_mean = s6_qc.head(half)["dimension_deviation_mm"].mean()
    second_mean = s6_qc.tail(half)["dimension_deviation_mm"].mean()
    drift = second_mean - first_mean

    assert drift > 0.05, (
        f"Drift insuffisant: first_half={first_mean:.3f}, "
        f"second_half={second_mean:.3f}, drift={drift:.3f} (attendu >0.05)"
    )
    print(f"OK: Drift S006 visible ({len(s6_qc)} QC, "
          f"moyenne debut={first_mean:.3f}, fin={second_mean:.3f}, delta={drift:.3f})")


def run_all():
    tests = [
        ("01 - Fichiers existent", test_01_all_files_exist),
        ("02 - Colonnes ERP", test_02_orders_have_required_columns),
        ("03 - Cycles références OF", test_03_cycles_have_valid_order_refs),
        ("04 - Qualité références OF", test_04_quality_checks_have_valid_order_refs),
        ("05 - Maintenance machines", test_05_maintenance_refs_valid_machine),
        ("06 - 6 scénarios GT", test_06_ground_truth_has_6_scenarios),
        ("07 - Preuves scénarios", test_07_scenarios_have_evidence),
        ("08 - Cycles dans fenêtre", test_08_cycles_within_order_window),
        ("09 - 5+ types défauts", test_09_at_least_5_defect_types),
        ("10 - Données imparfaites", test_10_imperfect_data_exists),
        ("11 - 3 machines ERP", test_11_orders_cover_all_machines),
        ("12 - Défauts qualité/cycles", test_12_quality_defect_types_match_cycles),
        ("13 - Timestamps maintenance", test_13_maintenance_events_have_timestamps),
        ("14 - Preuves fenêtre ±2h", test_14_scenario_evidence_within_window),
        ("15 - Drift S006", test_15_s006_dimensional_drift),
    ]
    passed, failed = 0, 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"ECHEC [{name}]: {e}")
            failed += 1
        except Exception as e:
            print(f"ERREUR [{name}]: {type(e).__name__}: {e}")
            failed += 1
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"Résultat: {passed}/{total} tests réussis")
    if failed:
        print(f"ÉCHEC: {failed} test(s) en échec")
        exit(1)
    else:
        print("SUCCÈS: Tous les tests passent")


if __name__ == "__main__":
    run_all()
