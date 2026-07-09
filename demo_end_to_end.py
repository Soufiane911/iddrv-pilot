#!/usr/bin/env python3
"""
IDDRV — Démonstration end-to-end du pipeline d'ingestion
=========================================================

Ce script orchestre la démonstration complète du projet :

  Étape 1 : Génération des données d'exemples (ingest/generate_samples.py)
  Étape 2 : Setup de la base de données (db/setup_db.py)
  Étape 3 : Ingestion ERP puis fichiers machine via ingest_pipeline.py
  Étape 4 : Requêtes de validation (cycles/machine, TRS, anomalies)
  Étape 5 : Comparaison ERP vs Machine (cycle time théorique vs mesuré)

Usage :
    python demo_end_to_end.py
    DATABASE_URL=postgresql://... python demo_end_to_end.py
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.resolve()
INGEST_DIR   = PROJECT_ROOT / "ingest"
DB_DIR       = PROJECT_ROOT / "db"
SAMPLES_DIR  = PROJECT_ROOT / "data" / "samples"

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iddrv_user:iddrv_secret_2024@localhost:5432/iddrv"
)

ERP_FILE = "erp_trs_fevrier.xlsx"

# Fichiers machine à ingérer avec leur référence ERP
MACHINE_FILES = [
    ("arburg_1003_cycles.txt",  "1003"),
    ("engel_152_cycles.csv",    "152"),
    ("transposed_606_tubes.txt","606"),
]

# ──────────────────────────────────────────────────────────────────────────────
# UI helpers
# ──────────────────────────────────────────────────────────────────────────────

RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
CYAN    = "\033[96m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"


def _header(step: int, title: str):
    print(f"\n{BOLD}{BLUE}{'━'*64}{RESET}")
    print(f"{BOLD}{BLUE}  ÉTAPE {step} — {title}{RESET}")
    print(f"{BOLD}{BLUE}{'━'*64}{RESET}")


def _ok(msg: str):
    print(f"  {GREEN}✅  {msg}{RESET}")


def _warn(msg: str):
    print(f"  {YELLOW}⚠️   {msg}{RESET}")


def _err(msg: str):
    print(f"  {RED}❌  {msg}{RESET}")


def _info(msg: str):
    print(f"  {CYAN}ℹ️   {msg}{RESET}")


def _section(title: str):
    print(f"\n  {MAGENTA}{BOLD}{title}{RESET}")
    print(f"  {'─'*55}")


def _table_row(label: str, value, width: int = 35):
    label_str = f"{label}:".ljust(width)
    print(f"    {CYAN}{label_str}{RESET} {BOLD}{value}{RESET}")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de subprocess
# ──────────────────────────────────────────────────────────────────────────────

def run_script(script_path: Path, args: list = None, cwd: Path = None) -> bool:
    """Exécute un script Python et retourne True si succès."""
    cmd = [sys.executable, str(script_path)] + (args or [])
    env = {**os.environ, "DATABASE_URL": DB_URL}

    result = subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        env=env,
        capture_output=False,   # Affiche la sortie en direct
        text=True
    )
    return result.returncode == 0


# ──────────────────────────────────────────────────────────────────────────────
# Connexion base de données
# ──────────────────────────────────────────────────────────────────────────────

def get_connection():
    """Retourne une connexion psycopg2 à la base IDDRV."""
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DB_URL)
        return conn
    except ImportError:
        _err("psycopg2 non installé. Exécutez : pip install psycopg2-binary")
        sys.exit(1)
    except Exception as exc:
        _err(f"Impossible de se connecter à la base : {exc}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# ÉTAPE 1 — Génération des données d'exemples
# ──────────────────────────────────────────────────────────────────────────────

def step1_generate_samples() -> bool:
    _header(1, "Génération des données d'exemples")
    script = INGEST_DIR / "generate_samples.py"

    if not script.exists():
        _err(f"Script introuvable : {script}")
        return False

    _info(f"Exécution de {script.relative_to(PROJECT_ROOT)} …")
    success = run_script(script, cwd=PROJECT_ROOT)

    if success:
        generated = list(SAMPLES_DIR.glob("*"))
        _ok(f"{len(generated)} fichiers générés dans {SAMPLES_DIR.relative_to(PROJECT_ROOT)}/")
        for f in sorted(generated):
            size_kb = f.stat().st_size / 1024
            print(f"       📄  {f.name} ({size_kb:.1f} Ko)")
    else:
        _err("Échec de la génération des données")

    return success


# ──────────────────────────────────────────────────────────────────────────────
# ÉTAPE 2 — Setup de la base de données
# ──────────────────────────────────────────────────────────────────────────────

def step2_setup_db() -> bool:
    _header(2, "Initialisation de la base de données")
    script = DB_DIR / "setup_db.py"

    if not script.exists():
        _err(f"Script introuvable : {script}")
        return False

    _info(f"Exécution de {script.relative_to(PROJECT_ROOT)} …")
    success = run_script(script, cwd=PROJECT_ROOT)

    if not success:
        _warn("setup_db.py a retourné un code d'erreur (base peut-être déjà initialisée)")
        # On continue quand même — la base peut déjà exister

    return True  # Non-bloquant


# ──────────────────────────────────────────────────────────────────────────────
# ÉTAPE 3 — Ingestion ERP et fichiers machine
# ──────────────────────────────────────────────────────────────────────────────

def step3_ingest_files() -> dict:
    _header(3, "Ingestion ERP et fichiers machine")
    script = INGEST_DIR / "ingest_pipeline.py"
    results = {}

    if not script.exists():
        _err(f"Script introuvable : {script}")
        return results

    erp_path = SAMPLES_DIR / ERP_FILE
    if erp_path.exists():
        _info(f"Ingestion ERP de {ERP_FILE} …")
        erp_success = run_script(
            script,
            args=["--erp", str(erp_path)],
            cwd=INGEST_DIR
        )
        results[ERP_FILE] = erp_success
        if erp_success:
            _ok(f"{ERP_FILE} ingéré avec succès")
        else:
            _warn(f"{ERP_FILE} : ingestion terminée (vérifiez les logs ci-dessus)")
    else:
        _warn(f"Fichier ERP absent : {ERP_FILE} — la comparaison ERP/Machine sera limitée")
        results[ERP_FILE] = False

    for filename, machine_ref in MACHINE_FILES:
        file_path = SAMPLES_DIR / filename
        if not file_path.exists():
            _warn(f"Fichier absent : {filename} — ignoré")
            results[filename] = False
            continue

        _info(f"Ingestion de {filename} (machine {machine_ref}) …")
        success = run_script(
            script,
            args=[str(file_path), machine_ref],
            cwd=INGEST_DIR          # ingest_pipeline.py utilise des imports relatifs
        )
        results[filename] = success
        if success:
            _ok(f"{filename} ingéré avec succès")
        else:
            _warn(f"{filename} : ingestion terminée (vérifiez les logs ci-dessus)")

    return results


# ──────────────────────────────────────────────────────────────────────────────
# ÉTAPE 4 — Requêtes de validation
# ──────────────────────────────────────────────────────────────────────────────

def step4_query_summary():
    _header(4, "Résumé de la base de données")
    import psycopg2.extras

    conn = get_connection()
    if not conn:
        return

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ── 4a. Cycles par machine ──────────────────────────────────────────────
    _section("Cycles ingérés par machine")
    cursor.execute("""
        SELECT
            m.erp_ref,
            m.name,
            m.brand,
            COUNT(mc.time)                              AS total_cycles,
            ROUND(AVG(mc.cycle_time_s)::NUMERIC, 2)    AS avg_cycle_s,
            ROUND(MIN(mc.cycle_time_s)::NUMERIC, 2)    AS min_cycle_s,
            ROUND(MAX(mc.cycle_time_s)::NUMERIC, 2)    AS max_cycle_s,
            SUM(CASE WHEN mc.scrap_flag THEN 1 ELSE 0 END) AS total_rebuts,
            ROUND(AVG(mc.link_confidence)::NUMERIC, 3) AS avg_confidence
        FROM machines m
        LEFT JOIN machine_cycles mc ON mc.machine_id = m.id
        GROUP BY m.id, m.erp_ref, m.name, m.brand
        ORDER BY total_cycles DESC
    """)
    rows = cursor.fetchall()

    print(f"\n    {'Machine':<10} {'Marque':<12} {'Cycles':>8} {'Avg Cycle':>10} {'Rebuts':>7} {'Confiance':>10}")
    print(f"    {'─'*10} {'─'*12} {'─'*8} {'─'*10} {'─'*7} {'─'*10}")
    for r in rows:
        cycles = r["total_cycles"] or 0
        avg    = f"{r['avg_cycle_s']} s" if r["avg_cycle_s"] else "—"
        rebuts = r["total_rebuts"] or 0
        conf   = f"{float(r['avg_confidence']):.1%}" if r["avg_confidence"] else "—"
        print(f"    {r['erp_ref']:<10} {r['brand'] or '—':<12} {cycles:>8} {avg:>10} {rebuts:>7} {conf:>10}")

    # ── 4b. TRS calculé ────────────────────────────────────────────────────
    _section("TRS calculé (Taux de Rendement Synthétique)")
    _info("Le TRS machine est estimé depuis les cycles : TRS ≈ (bonnes pièces × cycle théorique ERP) / temps disponible")
    cursor.execute("""
        SELECT
            m.erp_ref,
            m.name,
            COUNT(mc.time)                                          AS total_cycles,
            COUNT(mc.time) FILTER (WHERE NOT mc.scrap_flag)        AS good_cycles,
            ROUND((COUNT(mc.time) FILTER (WHERE NOT mc.scrap_flag)::NUMERIC
                   / NULLIF(COUNT(mc.time), 0) * 100), 1)          AS taux_qualite_pct,
            ROUND(AVG(mc.cycle_time_s)::NUMERIC, 2)                AS avg_cycle_s,
            COUNT(mc.time) FILTER (WHERE mc.quality_flag != 'valid') AS anomalies
        FROM machines m
        JOIN machine_cycles mc ON mc.machine_id = m.id
        GROUP BY m.id, m.erp_ref, m.name
        HAVING COUNT(mc.time) > 0
        ORDER BY m.erp_ref
    """)
    trs_rows = cursor.fetchall()

    for r in trs_rows:
        print()
        _table_row(f"Machine {r['erp_ref']} — {r['name']}", "")
        _table_row("  Total cycles", r["total_cycles"])
        _table_row("  Bonnes pièces", r["good_cycles"])
        _table_row("  Taux qualité", f"{r['taux_qualite_pct']} %")
        _table_row("  Cycle moyen mesuré", f"{r['avg_cycle_s']} s")
        _table_row("  Anomalies détectées", r["anomalies"])

    # ── 4c. Anomalies globales ─────────────────────────────────────────────
    _section("Anomalies et problèmes de qualité")
    cursor.execute("""
        SELECT issue_type, severity, COUNT(*) AS nb
        FROM data_quality_issues
        GROUP BY issue_type, severity
        ORDER BY nb DESC
    """)
    issues = cursor.fetchall()

    if issues:
        col_header = "Type d'anomalie"
        print(f"\n    {col_header:<30} {'Sévérité':<10} {'Nb':>5}")
        print(f"    {'─'*30} {'─'*10} {'─'*5}")
        for i in issues:
            print(f"    {i['issue_type']:<30} {i['severity']:<10} {i['nb']:>5}")
    else:
        _ok("Aucune anomalie de qualité enregistrée")

    # ── 4d. Passeports d'import ────────────────────────────────────────────
    _section("Passeports d'import")
    cursor.execute("""
        SELECT file_name, brand_detected, row_count_accepted, row_count_rejected,
               column_mapping_confidence, imported_at
        FROM import_passports
        ORDER BY imported_at DESC
    """)
    passports = cursor.fetchall()

    if passports:
        for p in passports:
            accepted  = p["row_count_accepted"] or 0
            rejected  = p["row_count_rejected"] or 0
            total     = accepted + rejected
            conf      = float(p["column_mapping_confidence"] or 0)
            ts        = p["imported_at"].strftime("%Y-%m-%d %H:%M:%S") if p["imported_at"] else "—"
            print()
            _table_row(f"  {p['file_name']}", "")
            _table_row("    Marque détectée", p["brand_detected"])
            _table_row("    Cycles acceptés", f"{accepted}/{total}")
            _table_row("    Confiance mapping", f"{conf:.0%}")
            _table_row("    Importé le", ts)
    else:
        _warn("Aucun passeport d'import trouvé (les fichiers n'ont peut-être pas été ingérés)")

    cursor.close()
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# ÉTAPE 5 — Comparaison ERP vs Machine
# ──────────────────────────────────────────────────────────────────────────────

def step5_erp_vs_machine():
    _header(5, "Comparaison ERP vs Machine (cycle time théorique vs mesuré)")
    import psycopg2.extras

    conn = get_connection()
    if not conn:
        return

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    _section("Cycle time ERP théorique vs Machine mesuré")

    cursor.execute("""
        SELECT
            m.erp_ref,
            m.name                                              AS machine_name,
            po.id                                               AS of_id,
            po.product_ref,
            po.erp_cycle_time_s                                AS erp_cycle_s,
            ROUND(AVG(mc.cycle_time_s)::NUMERIC, 3)            AS machine_avg_cycle_s,
            COUNT(mc.time)                                      AS machine_cycle_count,
            ROUND(
                ((AVG(mc.cycle_time_s) - po.erp_cycle_time_s)
                 / NULLIF(po.erp_cycle_time_s, 0) * 100)::NUMERIC,
                1
            )                                                   AS delta_pct
        FROM production_orders po
        JOIN machines m ON m.id = po.machine_id
        LEFT JOIN machine_cycles mc
            ON mc.machine_id = po.machine_id
           AND mc.production_order_id = po.id
        WHERE po.erp_cycle_time_s IS NOT NULL
        GROUP BY m.erp_ref, m.name, po.id, po.product_ref, po.erp_cycle_time_s
        HAVING COUNT(mc.time) > 0
        ORDER BY ABS(
            ((AVG(mc.cycle_time_s) - po.erp_cycle_time_s)
             / NULLIF(po.erp_cycle_time_s, 0) * 100)
        ) DESC
        LIMIT 15
    """)
    comparisons = cursor.fetchall()

    if comparisons:
        print(f"\n    {'OF':<18} {'Machine':<8} {'ERP (s)':>8} {'Mesuré (s)':>11} {'Δ (%)':>8} {'Cycles':>7}")
        print(f"    {'─'*18} {'─'*8} {'─'*8} {'─'*11} {'─'*8} {'─'*7}")
        for r in comparisons:
            erp_s    = f"{r['erp_cycle_s']:.2f}" if r["erp_cycle_s"] else "—"
            mach_s   = f"{r['machine_avg_cycle_s']:.2f}" if r["machine_avg_cycle_s"] else "—"
            delta    = r["delta_pct"]
            cycles   = r["machine_cycle_count"]
            if delta is not None:
                delta_str = f"{float(delta):+.1f}%"
                # Coloration selon l'écart
                if abs(float(delta)) > 10:
                    delta_str = f"{RED}{delta_str}{RESET}"
                elif abs(float(delta)) > 5:
                    delta_str = f"{YELLOW}{delta_str}{RESET}"
                else:
                    delta_str = f"{GREEN}{delta_str}{RESET}"
            else:
                delta_str = "—"
            of_id_short = (r["of_id"] or "—")[:18]
            print(f"    {of_id_short:<18} {r['erp_ref']:<8} {erp_s:>8} {mach_s:>11} {delta_str:>8} {cycles:>7}")
    else:
        _warn("Aucune correspondance ERP ↔ Machine trouvée (OFs non réconciliés)")
        _info("Les cycles machine ont été ingérés sans OF ERP associé dans cet exemple")

        # Affichage de synthèse alternative sans réconciliation
        cursor.execute("""
            SELECT
                m.erp_ref,
                m.name,
                COUNT(mc.time)                             AS total_cycles,
                ROUND(AVG(mc.cycle_time_s)::NUMERIC, 3)   AS avg_cycle_s,
                ROUND(STDDEV(mc.cycle_time_s)::NUMERIC, 3) AS stddev_cycle_s
            FROM machines m
            JOIN machine_cycles mc ON mc.machine_id = m.id
            GROUP BY m.id, m.erp_ref, m.name
            HAVING COUNT(mc.time) > 0
            ORDER BY m.erp_ref
        """)
        alt = cursor.fetchall()
        if alt:
            print()
            _info("Synthèse des cycles machine ingérés (sans réconciliation ERP) :")
            print(f"\n    {'Machine':<10} {'Nom':<25} {'Cycles':>8} {'Avg (s)':>9} {'σ (s)':>8}")
            print(f"    {'─'*10} {'─'*25} {'─'*8} {'─'*9} {'─'*8}")
            for r in alt:
                print(f"    {r['erp_ref']:<10} {r['name']:<25} {r['total_cycles']:>8} "
                      f"{r['avg_cycle_s']:>9} {r['stddev_cycle_s'] or '—':>8}")

    cursor.close()
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Récapitulatif final
# ──────────────────────────────────────────────────────────────────────────────

def print_final_summary(t_start: float, ingestion_results: dict):
    elapsed = time.time() - t_start

    print(f"\n{BOLD}{GREEN}{'═'*64}{RESET}")
    print(f"{BOLD}{GREEN}  DÉMONSTRATION IDDRV TERMINÉE{RESET}")
    print(f"{BOLD}{GREEN}{'═'*64}{RESET}")

    success_count = sum(1 for v in ingestion_results.values() if v)
    total_count   = len(ingestion_results)

    _table_row("Durée totale", f"{elapsed:.1f} s", 30)
    _table_row("Fichiers ingérés", f"{success_count}/{total_count}", 30)

    print(f"\n  {CYAN}Pour aller plus loin :{RESET}")
    print(f"    • Lancer le pipeline sur vos propres fichiers :")
    print(f"      {BOLD}python ingest/ingest_pipeline.py <fichier> <ref_machine>{RESET}")
    print(f"    • Se connecter à la base :")
    print(f"      {BOLD}psql \"{DB_URL}\"{RESET}")
    print(f"    • Exécuter les tests :")
    print(f"      {BOLD}cd ingest && python -m pytest ../tests/test_ingestion.py -v{RESET}")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    t_start = time.time()

    print(f"\n{BOLD}{MAGENTA}{'╔' + '═'*62 + '╗'}{RESET}")
    print(f"{BOLD}{MAGENTA}║{'  IDDRV — Démonstration End-to-End':^62}║{RESET}")
    print(f"{BOLD}{MAGENTA}║{'  Industrial Data Ingestion & Reconciliation Vault':^62}║{RESET}")
    print(f"{BOLD}{MAGENTA}{'╚' + '═'*62 + '╝'}{RESET}")
    print(f"\n  {CYAN}Démarré le : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"  {CYAN}Base cible  : {DB_URL.split('@')[-1]}{RESET}")

    # Étape 1 : Génération des samples
    ok1 = step1_generate_samples()
    if not ok1:
        _err("Impossible de générer les données d'exemples. Abandon.")
        sys.exit(1)

    # Étape 2 : Setup DB
    step2_setup_db()

    # Étape 3 : Ingestion
    ingestion_results = step3_ingest_files()

    # Étape 4 : Résumé
    try:
        step4_query_summary()
    except Exception as exc:
        _warn(f"Requêtes de validation impossible (DB non disponible ?) : {exc}")

    # Étape 5 : Comparaison ERP vs Machine
    try:
        step5_erp_vs_machine()
    except Exception as exc:
        _warn(f"Comparaison ERP/Machine impossible : {exc}")

    # Récapitulatif
    print_final_summary(t_start, ingestion_results)


if __name__ == "__main__":
    main()
