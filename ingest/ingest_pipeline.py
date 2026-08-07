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
import csv
from types import SimpleNamespace
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from .profiler import profile_file
    from .loader import load_file, compute_file_hash, read_erp_trs_xlsx
    from .mapper import get_mapping_confidence
    from .reconciler import insert_cycles, get_db_connection, reconcile_existing_cycles
except ImportError:  # direct ``python ingest/ingest_pipeline.py`` compatibility
    from profiler import profile_file
    from loader import load_file, compute_file_hash, read_erp_trs_xlsx
    from mapper import get_mapping_confidence
    from reconciler import insert_cycles, get_db_connection, reconcile_existing_cycles

DB_URL = os.getenv("DATABASE_URL", "postgresql://iddrv_user@localhost:5432/iddrv")
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


def _source_datetime(value, source_timezone: str) -> datetime | None:
    parsed = _as_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(source_timezone))
    return parsed.astimezone(timezone.utc)


def _row_hash(row: dict) -> str:
    encoded = json.dumps(row, sort_keys=True, default=_json_default, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _rows_hash(rows: list[dict]) -> str:
    encoded = json.dumps(rows, sort_keys=True, default=_json_default, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def resolve_machine_id(cursor, erp_ref: str, site_id: int) -> int | None:
    """Résout un identifiant machine ERP vers l'id interne, strictement isolé par site.

    La résolution cherche d'abord dans la table machines (scopée par site_id),
    puis dans les alias de machines (scopés via la FK machine -> site).
    Si deux sites partagent la même référence ERP, seul le machine_id du bon
    site est retourné.

    Lève ValueError si site_id est None ou absent.
    """
    if site_id is None:
        raise ValueError("site_id obligatoire pour la résolution machine")

    cursor.execute("""
        WITH candidates AS (
            SELECT m.id FROM machines m
            WHERE m.site_id = %s AND m.erp_ref = %s
            UNION
            SELECT ma.machine_id AS id FROM machine_aliases ma
            WHERE ma.site_id = %s AND ma.alias_value = %s
        )
        SELECT MIN(id) AS id, COUNT(*) AS candidate_count FROM candidates
    """, (site_id, erp_ref, site_id, erp_ref))
    row = cursor.fetchone()
    if not row or not row["candidate_count"]:
        return None
    if row["candidate_count"] > 1:
        raise ValueError(
            f"Référence machine ambiguë sur le site {site_id}: '{erp_ref}'"
        )
    return row["id"]


def create_import_passport(
    cursor,
    file_path: str,
    file_hash: str,
    profile,
    col_map: dict,
    rows: list,
    rows_accepted: int,
    rows_rejected: int,
    site_id: int | None = None
) -> str:
    """Enregistre le passeport d'import dans la base de données."""
    cursor.execute("""
        INSERT INTO import_passports (
            file_name, file_hash, file_path_raw,
            parser_type, brand_detected, encoding_detected,
            delimiter_detected, is_transposed,
            row_count_total, row_count_accepted, row_count_rejected,
            column_mapping_confidence, site_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        get_mapping_confidence(col_map),
        site_id
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


def _validate_site_id(site_id: int | None, context: str = "") -> int:
    """Refuse explicitement un import lorsque le site est ambigu ou absent."""
    if site_id is None:
        raise ValueError(
            f"site_id manquant pour l'import {context}. "
            f"Précisez --site-id ou positionnez le fichier sous inbox/<site>/"
        )
    if not isinstance(site_id, int) or site_id <= 0:
        raise ValueError(
            f"site_id invalide pour l'import {context}: {site_id}"
        )
    return site_id


def ingest_machine_file(
    file_path: str,
    machine_erp_ref: str,
    site_id: int | None = None,
    source_timezone: str | None = None,
):
    """
    Pipeline complet d'ingestion d'un fichier machine.

    Args:
        file_path: Chemin du fichier à ingérer.
        machine_erp_ref: Référence ERP de la machine (ex: '1003').
        site_id: Identifiant du site. Obligatoire pour l'isolation multi-site.
        source_timezone: Override explicite pour une source documentée en UTC.
    """
    site_id = _validate_site_id(site_id, f"fichier machine {machine_erp_ref}")
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {file_path}")

    print(f"\n{'='*60}")
    print(f" INGESTION: {path.name} (site {site_id})")
    print(f"{'='*60}")

    # 1. Hash du fichier
    file_hash = compute_file_hash(file_path)

    # 2. Connexion DB
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 3. Vérification déduplication (le fichier a déjà été importé ?)
    cursor.execute(
        "SELECT id, status FROM import_passports WHERE site_id = %s AND file_hash = %s",
        (site_id, file_hash),
    )
    existing = cursor.fetchone()
    if existing:
        if existing['status'] == 'completed':
            print(f"[SKIP] Fichier déjà importé avec succès (passport_id: {existing['id']})")
            cursor.close()
            conn.close()
            return {"transaction_committed": True, "passport_id": str(existing["id"]), "duplicate": True, "site_id": site_id}
        else:
            print(f"[RETRY] Fichier précédemment interrompu ou échoué (statut '{existing['status']}'). Nettoyage des anciennes données pour réimport...")
            cursor.execute("DELETE FROM machine_cycles WHERE passport_id = %s", (existing['id'],))
            cursor.execute("DELETE FROM data_quality_issues WHERE passport_id = %s", (existing['id'],))
            cursor.execute("DELETE FROM evidence_vault WHERE passport_id = %s", (existing['id'],))
            cursor.execute("DELETE FROM import_passports WHERE id = %s", (existing['id'],))
            conn.commit()

    # 4. Résolution machine_id
    machine_id = resolve_machine_id(cursor, machine_erp_ref, site_id)
    if not machine_id:
        cursor.close()
        conn.close()
        raise ValueError(f"Machine ERP '{machine_erp_ref}' introuvable sur le site {site_id}")

    # 5. Chargement et mapping avec le mapping versionné et le fuseau du site.
    cursor.execute("SELECT timezone FROM sites WHERE id=%s", (site_id,))
    site_row = cursor.fetchone()
    if site_row is None:
        cursor.close()
        conn.close()
        raise ValueError(f"Site inconnu: {site_id}")
    rows, profile, col_map = load_file(
        file_path,
        site_id=site_id,
        machine_erp_ref=machine_erp_ref,
        source_timezone=source_timezone or str(site_row["timezone"]),
    )

    # 6. Archivage du fichier brut dans RAW_STORE
    RAW_STORE.mkdir(parents=True, exist_ok=True)
    raw_dest = RAW_STORE / f"{file_hash[:12]}_{path.name}"
    if not raw_dest.exists():
        shutil.copy2(file_path, raw_dest)

    # 7. Création du passeport d'import
    accepted = [r for r in rows if r.get("time") is not None]
    rejected_count = len(rows) - len(accepted)
    if not accepted:
        cursor.close()
        conn.close()
        raise ValueError("Aucun cycle valide dans le fichier")

    passport_id = create_import_passport(
        cursor, file_path, file_hash, profile, col_map,
        rows, len(accepted), rejected_count, site_id=site_id
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
        inserted, skipped = insert_cycles(rows, machine_id, passport_id, site_id=site_id)

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
    return {
        "transaction_committed": True,
        "passport_id": passport_id,
        "site_id": site_id,
        "inserted": inserted,
        "skipped": skipped,
    }


def ingest_erp_file(
    file_path: str,
    site_id: int | None = None,
    source_timezone: str | None = None,
):
    """
    Ingestion ERP/TRS : alimente production_orders et shifts avant reconciliation.
    """
    site_id = _validate_site_id(site_id, f"fichier ERP {Path(file_path).name}")
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {file_path}")

    print(f"\n{'='*60}")
    print(f" INGESTION ERP: {path.name} (site {site_id})")
    print(f"{'='*60}")

    raw_file_hash = compute_file_hash(file_path)
    orders = read_erp_trs_xlsx(file_path)
    if not orders:
        raise ValueError("Aucun ordre ERP valide dans le fichier")
    file_hash = raw_file_hash
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        "SELECT id, status FROM import_passports WHERE site_id = %s AND file_hash = %s",
        (site_id, file_hash),
    )
    existing = cursor.fetchone()
    if existing:
        if existing['status'] == 'completed':
            print(f"[SKIP] Fichier ERP déjà importé (passport_id: {existing['id']})")
            cursor.close()
            conn.close()
            try:
                reconciled_cycles = reconcile_existing_cycles(site_id=site_id)
                post_commit_error = None
            except Exception as exc:
                reconciled_cycles = 0
                post_commit_error = f"erp_reconciliation_failed:{exc}"
            return {
                "transaction_committed": True,
                "passport_id": str(existing["id"]),
                "duplicate": True,
                "site_id": site_id,
                "reconciled_cycles": reconciled_cycles,
                "post_commit_error": post_commit_error,
            }
        else:
            print(f"[RETRY] Rejeu idempotent du fichier ERP (statut '{existing['status']}')")
            # Never delete existing business OFs on retry. The passport and its
            # staging rows are replaced inside the same transaction as upserts.
            cursor.execute("DELETE FROM import_passports WHERE id = %s", (existing['id'],))

    cursor.execute("SELECT timezone FROM sites WHERE id=%s", (site_id,))
    site_row = cursor.fetchone()
    if site_row is None:
        cursor.close()
        conn.close()
        raise ValueError(f"Site inconnu: {site_id}")
    source_tz = source_timezone or str(site_row["timezone"])

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
        len([o for o in orders if not (o.get("id") and o.get("machine_erp_ref"))]),
        site_id=site_id
    )
    stage_rows(cursor, passport_id, orders, "erp_order")

    inserted_orders = 0
    inserted_shifts = 0
    rejected = 0
 
    # Shifts are upserted in place so existing cycle.shift_id references stay
    # stable across ERP retries and refreshed exports.

    for order in orders:
        machine_ref = str(order.get("machine_erp_ref", "")).strip()
        machine_id = resolve_machine_id(cursor, machine_ref, site_id)
        started_at = _source_datetime(order.get("started_at"), source_tz)
        ended_at = _source_datetime(order.get("ended_at"), source_tz)
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
                id, site_id, machine_id, product_ref, product_name, tool_ref, material_ref,
                target_quantity, started_at, ended_at, erp_cycle_time_s, erp_trs,
                erp_scrap_count, erp_good_parts, erp_available_time_h, erp_running_time_h
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (site_id, id) DO UPDATE SET
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
            site_id,
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
                    machine_id, production_order_id, order_site_id, shift_number, shift_date,
                    started_at, ended_at, planned_duration_h
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (machine_id, shift_date, shift_number) DO UPDATE SET
                    production_order_id = EXCLUDED.production_order_id,
                    order_site_id = EXCLUDED.order_site_id,
                    started_at = EXCLUDED.started_at,
                    ended_at = EXCLUDED.ended_at,
                    planned_duration_h = EXCLUDED.planned_duration_h
            """, (
                machine_id,
                str(order["id"]),
                site_id,
                int(order["shift_number"]),
                started_at.date(),
                started_at,
                ended_at,
                order.get("erp_available_time_h")
            ))
            inserted_shifts += 1

    try:
        # Passport, OFs and shifts become visible atomically.
        cursor.execute(
            "UPDATE import_passports SET status='completed',row_count_rejected=%s WHERE id=%s",
            (rejected, passport_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    try:
        reconciled_cycles = reconcile_existing_cycles(site_id=site_id)
        post_commit_error = None
    except Exception as exc:
        # Business rows are committed; the watcher must retry this idempotent
        # phase without consuming the import/quarantine attempt budget.
        reconciled_cycles = 0
        post_commit_error = f"erp_reconciliation_failed:{exc}"
        conn_pending = get_db_connection()
        with conn_pending.cursor() as cur_pending:
            cur_pending.execute(
                "UPDATE import_passports SET error_log=%s WHERE id=%s",
                (post_commit_error, passport_id),
            )
            conn_pending.commit()
        conn_pending.close()

    print(
        f"[ERP] {inserted_orders} OF insérés/mis à jour, "
        f"{inserted_shifts} équipes, {rejected} rejets, "
        f"{reconciled_cycles} cycles rattachés"
    )
    return {
        "transaction_committed": True,
        "passport_id": passport_id,
        "site_id": site_id,
        "inserted_orders": inserted_orders,
        "inserted_shifts": inserted_shifts,
        "rejected": rejected,
        "reconciled_cycles": reconciled_cycles,
        "post_commit_error": post_commit_error,
    }


def ingest_context_file(
    file_path: str,
    kind: str,
    site_id: int | None = None,
    source_timezone: str | None = None,
):
    """Import quality/maintenance/operator CSVs with stable IDs and provenance."""
    site_id = _validate_site_id(site_id, f"fichier contexte {kind}")
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {file_path}")
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    if not rows:
        raise ValueError("Aucune ligne de contexte valide dans le fichier")
    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    file_hash = compute_file_hash(file_path)
    cur.execute(
        "SELECT id FROM import_passports WHERE site_id=%s AND file_hash=%s AND status='completed'",
        (site_id, file_hash),
    )
    existing = cur.fetchone()
    if existing:
        cur.close(); conn.close()
        return {"transaction_committed": True, "passport_id": str(existing["id"]), "duplicate": True, "site_id": site_id}
    cur.execute("SELECT timezone FROM sites WHERE id=%s", (site_id,))
    site_row = cur.fetchone()
    if site_row is None:
        cur.close(); conn.close()
        raise ValueError(f"Site inconnu: {site_id}")
    source_tz = source_timezone or str(site_row["timezone"])
    profile = SimpleNamespace(brand_detected=kind, is_transposed=False, encoding="utf-8", delimiter=",")
    passport = create_import_passport(cur, file_path, file_hash, profile, {}, rows, len(rows), 0, site_id=site_id)
    inserted = 0
    rejected = 0
    for n, row in enumerate(rows, 1):
        mid = resolve_machine_id(cur, str(row.get("machine_erp_ref", "")), site_id)
        ts = _source_datetime(row.get("timestamp"), source_tz); oid = row.get("production_order_id") or None
        order_valid = True
        if oid:
            cur.execute(
                "SELECT 1 FROM production_orders WHERE site_id=%s AND id=%s",
                (site_id, oid),
            )
            order_valid = cur.fetchone() is not None
        if mid is None or ts is None or not order_valid:
            rejected += 1
            cur.execute(
                """INSERT INTO import_rejections
                     (passport_id,severity,error_code,field_name,raw_value,message)
                   VALUES (%s,'error','invalid_context_row','machine_erp_ref',%s,%s)""",
                (
                    passport,
                    str(row.get("machine_erp_ref", "")),
                    "Machine, OF ou timestamp invalide pour ce site",
                ),
            )
            cur.execute(
                """INSERT INTO staging_import_rows
                     (passport_id,source_line_no,source_kind,raw_data,normalized_data,source_row_hash,status)
                   VALUES (%s,%s,%s,%s,%s,%s,'rejected') ON CONFLICT DO NOTHING""",
                (
                    passport, n,
                    {"quality": "quality_check", "maintenance": "maintenance_event", "notes": "operator_note"}[kind],
                    json.dumps(row), json.dumps(row), _row_hash(row),
                ),
            )
            continue
        if kind == "quality":
            sql = """INSERT INTO quality_checks (quality_check_id,site_id,time,production_order_id,order_site_id,machine_id,product_ref,sample_size,defect_count,defect_type,severity,measured_weight_g,target_weight_g,dimension_deviation_mm,visual_result,comment,passport_id,source_row_hash,part_quality_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING"""
            vals = (row.get("quality_check_id"),site_id,ts,oid,site_id,mid,row.get("product_ref"),row.get("sample_size") or None,row.get("defect_count") or None,row.get("defect_type") or None,row.get("severity"),row.get("measured_weight_g") or None,row.get("target_weight_g") or None,row.get("dimension_deviation_mm") or None,row.get("visual_result"),row.get("comment"),passport,_row_hash(row),"defective" if int(row.get("defect_count") or 0)>0 else "conforming")
        elif kind == "maintenance":
            sql = """INSERT INTO maintenance_events (event_id,site_id,time,machine_id,production_order_id,order_site_id,event_type,duration_min,severity,description,passport_id,source_row_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING"""
            vals = (row.get("event_id"),site_id,ts,mid,oid,site_id,row.get("event_type"),row.get("duration_min") or None,row.get("severity"),row.get("description"),passport,_row_hash(row))
        else:
            sql = """INSERT INTO operator_notes (note_id,site_id,time,machine_id,production_order_id,order_site_id,operator_id,note_text,passport_id,source_row_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING"""
            vals = (row.get("note_id"),site_id,ts,mid,oid,site_id,row.get("operator_id"),row.get("note_text"),passport,_row_hash(row))
        cur.execute(sql, vals)
        inserted += cur.rowcount
        staging_kind = {"quality": "quality_check", "maintenance": "maintenance_event", "notes": "operator_note"}[kind]
        cur.execute("INSERT INTO staging_import_rows (passport_id,source_line_no,source_kind,raw_data,normalized_data,source_row_hash,status) VALUES (%s,%s,%s,%s,%s,%s,'accepted') ON CONFLICT DO NOTHING", (passport,n,staging_kind,json.dumps(row),json.dumps(row),_row_hash(row)))
    cur.execute(
        """UPDATE import_passports
           SET status='completed',row_count_accepted=%s,row_count_rejected=%s
           WHERE id=%s""",
        (inserted, rejected, passport),
    )
    conn.commit(); cur.close(); conn.close()
    return {
        "transaction_committed": True,
        "passport_id": passport,
        "site_id": site_id,
        "inserted": inserted,
        "rejected": rejected,
    }


def ingest_scenario(directory: str, site_id: int | None = None):
    """Import the complete industrial_demo scenario (ground_truth is never read)."""
    site_id = _validate_site_id(site_id, f"scénario {directory}")
    root = Path(directory)
    ingest_erp_file(str(root / "erp_orders.xlsx"), site_id=site_id, source_timezone="UTC")
    for machine in ("152", "1003", "606"):
        # The bundled synthetic fixture is generated on an explicit UTC axis.
        ingest_machine_file(
            str(root / f"machine_cycles_{machine}.csv"),
            machine,
            site_id=site_id,
            source_timezone="UTC",
        )
    ingest_context_file(str(root / "quality_checks.csv"), "quality", site_id=site_id, source_timezone="UTC")
    ingest_context_file(str(root / "maintenance_events.csv"), "maintenance", site_id=site_id, source_timezone="UTC")
    ingest_context_file(str(root / "operator_notes.csv"), "notes", site_id=site_id, source_timezone="UTC")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--probe":
        # Qualification is deliberately delegated to the pure probe module;
        # this branch never opens PostgreSQL or creates an import passport.
        try:
            from ingest.probe import main as probe_main
        except ModuleNotFoundError:
            # ``python ingest/ingest_pipeline.py`` puts only ``ingest/`` on
            # sys.path; add the project root for package-style probe imports.
            sys.path.insert(0, str(PROJECT_ROOT))
            from ingest.probe import main as probe_main
        raise SystemExit(probe_main(sys.argv[2:]))
    elif len(sys.argv) >= 3 and sys.argv[1] == "--erp":
        site_id = int(sys.argv[3]) if len(sys.argv) >= 4 else None
        ingest_erp_file(sys.argv[2], site_id=site_id)
    elif len(sys.argv) >= 3 and sys.argv[1] == "--scenario":
        site_id = int(sys.argv[3]) if len(sys.argv) >= 4 else None
        ingest_scenario(sys.argv[2], site_id=site_id)
    elif len(sys.argv) >= 3:
        file_arg = sys.argv[1]
        machine_ref = sys.argv[2]
        site_id = int(sys.argv[3]) if len(sys.argv) >= 4 else None
        ingest_machine_file(file_arg, machine_ref, site_id=site_id)
    else:
        print("Usage machine: python ingest_pipeline.py <fichier> <ref_machine_erp> [<site_id>]")
        print("Usage ERP    : python ingest_pipeline.py --erp <fichier_erp.xlsx> [<site_id>]")
        print("Usage scenario: python ingest_pipeline.py --scenario <dir> [<site_id>]")
        sys.exit(1)
