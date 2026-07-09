"""
IDDRV — Script principal d'ingestion
=====================================

Orchestre l'ingestion complète d'un fichier machine ou ERP :
1. Profiling (détection de format)
2. Chargement et mapping
3. Création du passeport d'import
4. Réconciliation temporelle ERP ↔ cycles
5. Insertion en base de données
"""

import os
import sys
import json
import hashlib
import shutil
from types import SimpleNamespace
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from pathlib import Path

from profiler import profile_file
from loader import load_file, compute_file_hash, read_erp_trs_xlsx
from mapper import get_mapping_confidence
from reconciler import insert_cycles, get_db_connection, reconcile_existing_cycles

DB_URL = os.getenv("DATABASE_URL", "postgresql://iddrv_user:iddrv_secret_2024@localhost:5432/iddrv")
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
RAW_STORE = Path(os.getenv("RAW_STORE_PATH", str(PROJECT_ROOT / "data" / "raw")))


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _as_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat"}:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _row_hash(row: dict) -> str:
    encoded = json.dumps(row, sort_keys=True, default=_json_default, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _rows_hash(rows: list[dict]) -> str:
    encoded = json.dumps(rows, sort_keys=True, default=_json_default, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def resolve_machine_id(cursor, erp_ref: str) -> int | None:
    """Résout un identifiant machine ERP vers l'id interne."""
    cursor.execute("""
        SELECT m.id FROM machines m
        WHERE m.erp_ref = %s
        UNION
        SELECT ma.machine_id FROM machine_aliases ma
        WHERE ma.alias_value = %s
        LIMIT 1
    """, (erp_ref, erp_ref))
    row = cursor.fetchone()
    return row["id"] if row else None


def create_import_passport(
    cursor,
    file_path: str,
    file_hash: str,
    profile,
    col_map: dict,
    rows: list,
    rows_accepted: int,
    rows_rejected: int
) -> str:
    """Enregistre le passeport d'import dans la base de données."""
    cursor.execute("""
        INSERT INTO import_passports (
            file_name, file_hash, file_path_raw,
            parser_type, brand_detected, encoding_detected,
            delimiter_detected, is_transposed,
            row_count_total, row_count_accepted, row_count_rejected,
            column_mapping_confidence
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        Path(file_path).name,
        file_hash,
        str(file_path),
        f"{profile.brand_detected}_protocol" if not profile.is_transposed else "transposed_utf16",
        profile.brand_detected,
        profile.encoding,
        repr(profile.delimiter),
        profile.is_transposed,
        len(rows),
        rows_accepted,
        rows_rejected,
        get_mapping_confidence(col_map)
    ))
    row = cursor.fetchone()
    return str(row["id"])


def stage_rows(cursor, passport_id: str, rows: list[dict], source_kind: str, required_time: bool = False):
    """Trace chaque ligne source en staging et ajoute source_line_no/source_row_hash aux lignes."""
    for line_no, row in enumerate(rows, start=1):
        source_row_hash = _row_hash(row)
        row["source_line_no"] = line_no
        row["source_row_hash"] = source_row_hash
        status = "accepted"
        error_code = None
        message = None

        if required_time and not row.get("time"):
            status = "rejected"
            error_code = "missing_timestamp"
            message = "Ligne machine sans horodatage canonique"
        elif source_kind == "erp_order" and not row.get("id"):
            status = "rejected"
            error_code = "missing_order_id"
            message = "Ligne ERP sans reference OF"

        cursor.execute("""
            INSERT INTO staging_import_rows (
                passport_id, source_line_no, source_kind,
                raw_data, normalized_data, source_row_hash, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (passport_id, source_line_no) DO NOTHING
            RETURNING id
        """, (
            passport_id,
            line_no,
            source_kind,
            json.dumps(row.get("raw_data", row), default=_json_default, ensure_ascii=False),
            json.dumps(row, default=_json_default, ensure_ascii=False),
            source_row_hash,
            status
        ))
        staged = cursor.fetchone()

        if error_code:
            cursor.execute("""
                INSERT INTO import_rejections (
                    passport_id, staging_row_id, severity, error_code, message
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                passport_id,
                staged["id"] if staged else None,
                "warning",
                error_code,
                message
            ))


def ingest_machine_file(file_path: str, machine_erp_ref: str):
    """
    Pipeline complet d'ingestion d'un fichier machine.
    
    Args:
        file_path: Chemin du fichier à ingérer.
        machine_erp_ref: Référence ERP de la machine (ex: '1003').
    """
    path = Path(file_path)
    if not path.exists():
        print(f"[ERREUR] Fichier introuvable: {file_path}")
        return

    print(f"\n{'='*60}")
    print(f" INGESTION: {path.name}")
    print(f"{'='*60}")

    # 1. Hash du fichier
    file_hash = compute_file_hash(file_path)

    # 2. Connexion DB
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 3. Vérification déduplication (le fichier a déjà été importé ?)
    cursor.execute("SELECT id, status FROM import_passports WHERE file_hash = %s", (file_hash,))
    existing = cursor.fetchone()
    if existing:
        if existing['status'] == 'completed':
            print(f"[SKIP] Fichier déjà importé avec succès (passport_id: {existing['id']})")
            cursor.close()
            conn.close()
            return
        else:
            print(f"[RETRY] Fichier précédemment interrompu ou échoué (statut '{existing['status']}'). Nettoyage des anciennes données pour réimport...")
            cursor.execute("DELETE FROM machine_cycles WHERE passport_id = %s", (existing['id'],))
            cursor.execute("DELETE FROM data_quality_issues WHERE passport_id = %s", (existing['id'],))
            cursor.execute("DELETE FROM evidence_vault WHERE passport_id = %s", (existing['id'],))
            cursor.execute("DELETE FROM import_passports WHERE id = %s", (existing['id'],))
            conn.commit()

    # 4. Résolution machine_id
    machine_id = resolve_machine_id(cursor, machine_erp_ref)
    if not machine_id:
        print(f"[ERREUR] Machine ERP '{machine_erp_ref}' introuvable en base")
        cursor.close()
        conn.close()
        return

    # 5. Chargement et mapping
    rows, profile, col_map = load_file(file_path)

    # 6. Archivage du fichier brut dans RAW_STORE
    RAW_STORE.mkdir(parents=True, exist_ok=True)
    raw_dest = RAW_STORE / f"{file_hash[:12]}_{path.name}"
    if not raw_dest.exists():
        shutil.copy2(file_path, raw_dest)

    # 7. Création du passeport d'import
    accepted = [r for r in rows if r.get("time") is not None]
    rejected_count = len(rows) - len(accepted)

    passport_id = create_import_passport(
        cursor, file_path, file_hash, profile, col_map,
        rows, len(accepted), rejected_count
    )
    stage_rows(cursor, passport_id, rows, "machine_cycle", required_time=True)
    conn.commit()

    print(f"[PASSPORT] Créé: {passport_id}")
    print(f"  Cycles valides: {len(accepted)} / {len(rows)}")
    print(f"  Confiance mapping: {get_mapping_confidence(col_map):.0%}")

    cursor.close()
    conn.close()

    # 8. Réconciliation et insertion
    try:
        insert_cycles(rows, machine_id, passport_id)
        
        # Mettre à jour le statut en 'completed'
        conn_completed = get_db_connection()
        with conn_completed.cursor() as cur_completed:
            cur_completed.execute("UPDATE import_passports SET status = 'completed' WHERE id = %s", (passport_id,))
            conn_completed.commit()
        conn_completed.close()
    except Exception as e:
        # Mettre à jour le statut en 'failed' et enregistrer l'erreur
        conn_failed = get_db_connection()
        with conn_failed.cursor() as cur_failed:
            cur_failed.execute("UPDATE import_passports SET status = 'failed', error_log = %s WHERE id = %s", (str(e), passport_id))
            conn_failed.commit()
        conn_failed.close()
        raise e

    print(f"[OK] Ingestion terminée pour {path.name}")


def ingest_erp_file(file_path: str):
    """
    Ingestion ERP/TRS : alimente production_orders et shifts avant reconciliation.
    """
    path = Path(file_path)
    if not path.exists():
        print(f"[ERREUR] Fichier introuvable: {file_path}")
        return

    print(f"\n{'='*60}")
    print(f" INGESTION ERP: {path.name}")
    print(f"{'='*60}")

    raw_file_hash = compute_file_hash(file_path)
    orders = read_erp_trs_xlsx(file_path)
    file_hash = _rows_hash(orders)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT id, status FROM import_passports WHERE file_hash = %s", (file_hash,))
    existing = cursor.fetchone()
    if existing:
        if existing['status'] == 'completed':
            print(f"[SKIP] Fichier ERP déjà importé (passport_id: {existing['id']})")
            cursor.close()
            conn.close()
            return
        else:
            print(f"[RETRY] Fichier ERP précédemment interrompu ou échoué (statut '{existing['status']}'). Nettoyage des anciennes données pour réimport...")
            cursor.execute("DELETE FROM shifts WHERE production_order_id IN (SELECT id FROM production_orders WHERE id IN (SELECT raw_data->>'id' FROM staging_import_rows WHERE passport_id = %s))", (existing['id'],))
            cursor.execute("DELETE FROM production_orders WHERE id IN (SELECT raw_data->>'id' FROM staging_import_rows WHERE passport_id = %s)", (existing['id'],))
            cursor.execute("DELETE FROM import_passports WHERE id = %s", (existing['id'],))
            conn.commit()

    RAW_STORE.mkdir(parents=True, exist_ok=True)
    raw_dest = RAW_STORE / f"{raw_file_hash[:12]}_{path.name}"
    if not raw_dest.exists():
        shutil.copy2(file_path, raw_dest)

    profile = SimpleNamespace(
        brand_detected="erp",
        is_transposed=False,
        encoding="xlsx",
        delimiter="",
    )
    passport_id = create_import_passport(
        cursor, file_path, file_hash, profile, {}, orders,
        len([o for o in orders if o.get("id") and o.get("machine_erp_ref")]),
        len([o for o in orders if not (o.get("id") and o.get("machine_erp_ref"))])
    )
    stage_rows(cursor, passport_id, orders, "erp_order")

    inserted_orders = 0
    inserted_shifts = 0
    rejected = 0
 
    # Supprimer les anciens shifts pour les ordres importés
    order_ids = [str(o["id"]) for o in orders if o.get("id")]
    if order_ids:
        cursor.execute("DELETE FROM shifts WHERE production_order_id = ANY(%s)", (order_ids,))

    for order in orders:
        machine_ref = str(order.get("machine_erp_ref", "")).strip()
        machine_id = resolve_machine_id(cursor, machine_ref)
        started_at = _as_datetime(order.get("started_at"))
        ended_at = _as_datetime(order.get("ended_at"))
        if not ended_at and started_at and order.get("erp_available_time_h"):
            ended_at = started_at + timedelta(hours=float(order["erp_available_time_h"]))

        if not order.get("id") or not machine_id or not started_at:
            rejected += 1
            cursor.execute("""
                INSERT INTO import_rejections (
                    passport_id, severity, error_code, field_name, raw_value, message
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                passport_id,
                "error",
                "invalid_erp_order",
                "machine_erp_ref",
                machine_ref,
                "OF ERP impossible à insérer : id, machine ou date de début manquante"
            ))
            continue

        cursor.execute("""
            INSERT INTO production_orders (
                id, machine_id, product_ref, product_name, tool_ref, material_ref,
                target_quantity, started_at, ended_at, erp_cycle_time_s, erp_trs,
                erp_scrap_count, erp_good_parts, erp_available_time_h, erp_running_time_h
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                machine_id = EXCLUDED.machine_id,
                product_ref = EXCLUDED.product_ref,
                product_name = EXCLUDED.product_name,
                tool_ref = EXCLUDED.tool_ref,
                material_ref = EXCLUDED.material_ref,
                target_quantity = EXCLUDED.target_quantity,
                started_at = EXCLUDED.started_at,
                ended_at = EXCLUDED.ended_at,
                erp_cycle_time_s = EXCLUDED.erp_cycle_time_s,
                erp_trs = EXCLUDED.erp_trs,
                erp_scrap_count = EXCLUDED.erp_scrap_count,
                erp_good_parts = EXCLUDED.erp_good_parts,
                erp_available_time_h = EXCLUDED.erp_available_time_h,
                erp_running_time_h = EXCLUDED.erp_running_time_h
        """, (
            str(order["id"]),
            machine_id,
            order.get("product_ref"),
            order.get("product_name"),
            order.get("tool_ref"),
            order.get("material_ref"),
            int(order["nb_cycles"]) if order.get("nb_cycles") is not None else None,
            started_at,
            ended_at,
            order.get("erp_cycle_time_s"),
            order.get("erp_trs"),
            int(order.get("erp_scrap_count", 0)),
            int(order.get("erp_good_parts", 0)),
            order.get("erp_available_time_h"),
            order.get("erp_running_time_h")
        ))
        inserted_orders += 1

        if order.get("shift_number") and ended_at:
            cursor.execute("""
                INSERT INTO shifts (
                    machine_id, production_order_id, shift_number, shift_date,
                    started_at, ended_at, planned_duration_h
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (machine_id, shift_date, shift_number) DO UPDATE SET
                    production_order_id = EXCLUDED.production_order_id,
                    started_at = EXCLUDED.started_at,
                    ended_at = EXCLUDED.ended_at,
                    planned_duration_h = EXCLUDED.planned_duration_h
            """, (
                machine_id,
                str(order["id"]),
                int(order["shift_number"]),
                started_at.date(),
                started_at,
                ended_at,
                order.get("erp_available_time_h")
            ))
            inserted_shifts += 1

    try:
        conn.commit()
        cursor.close()
        conn.close()

        reconciled_cycles = reconcile_existing_cycles()
        
        # Mettre à jour le statut en 'completed'
        conn_completed = get_db_connection()
        with conn_completed.cursor() as cur_completed:
            cur_completed.execute("UPDATE import_passports SET status = 'completed' WHERE id = %s", (passport_id,))
            conn_completed.commit()
        conn_completed.close()
        
        print(
            f"[ERP] {inserted_orders} OF insérés/mis à jour, "
            f"{inserted_shifts} équipes, {rejected} rejets, "
            f"{reconciled_cycles} cycles rattachés"
        )
    except Exception as e:
        # Mettre à jour le statut en 'failed' et enregistrer l'erreur
        conn_failed = get_db_connection()
        with conn_failed.cursor() as cur_failed:
            cur_failed.execute("UPDATE import_passports SET status = 'failed', error_log = %s WHERE id = %s", (str(e), passport_id))
            conn_failed.commit()
        conn_failed.close()
        raise e


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--erp":
        ingest_erp_file(sys.argv[2])
    elif len(sys.argv) >= 3:
        file_arg = sys.argv[1]
        machine_ref = sys.argv[2]
        ingest_machine_file(file_arg, machine_ref)
    else:
        print("Usage machine: python ingest_pipeline.py <fichier> <ref_machine_erp>")
        print("Usage ERP    : python ingest_pipeline.py --erp <fichier_erp.xlsx>")
        sys.exit(1)
