"""
IDDRV — Moteur de réconciliation temporelle ERP ↔ Cycles Machine
=================================================================

Associe chaque cycle machine (horodaté au cycle près) à l'Ordre de Fabrication (OF)
correspondant dans l'ERP, avec un score de confiance.

Algorithme :
1. Chercher les OFs actifs sur la même machine dans une fenêtre de ± 30 min.
2. Si un seul OF correspond → lien direct, confiance = 1.0.
3. Si plusieurs OFs se chevauchent → confiance proportionnelle à la distance.
4. Si aucun OF → production_order_id = NULL, confiance = 0.0.
"""

import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone
from typing import Optional
import os
import hashlib
import json


DB_URL = os.getenv("DATABASE_URL", "postgresql://iddrv_user:iddrv_secret_2024@localhost:5432/iddrv")
OVERLAP_WINDOW = timedelta(minutes=30)


def normalize_bool_flag(value, default=False) -> bool:
    """Normalise les booléens des CSV (True/False, 1/0) sans envoyer du texte SQL."""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "yes", "y", "oui"}


def normalize_good_parts(value) -> int:
    """Retourne 0/1 pour la colonne SMALLINT good_parts."""
    return 1 if normalize_bool_flag(value, default=True) else 0


def derive_part_quality(raw_data, scrap_flag) -> tuple[str, str | None]:
    """Retourne le statut pièce et le défaut canonique depuis la source brute."""
    source = str((raw_data or {}).get("quality_flag", "good")).strip()
    return ("scrap" if scrap_flag else "good", None if source.lower() in {"", "good", "ok", "valid"} else source)


def get_db_connection():
    """Retourne une connexion à la base de données PostgreSQL."""
    return psycopg2.connect(DB_URL)


def compute_source_row_hash(cycle: dict) -> str:
    """Calcule un hash stable pour identifier une ligne source normalisée."""
    payload = {
        k: v for k, v in cycle.items()
        if k not in {"source_line_no", "source_row_hash"}
    }
    encoded = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def resolve_of_for_cycle(
    cursor,
    machine_id: int,
    cycle_time: datetime,
    window: timedelta = OVERLAP_WINDOW
) -> tuple[Optional[str], float]:
    """
    Recherche l'OF correspondant pour un cycle donné.
    
    Retourne (production_order_id, link_confidence).
    """
    if cycle_time.tzinfo is None:
        cycle_time = cycle_time.replace(tzinfo=timezone.utc)

    window_start = cycle_time - window
    window_end = cycle_time + window

    cursor.execute("""
        SELECT id, started_at, ended_at
        FROM production_orders
        WHERE machine_id = %s
          AND started_at <= %s
          AND (ended_at IS NULL OR ended_at >= %s)
        ORDER BY started_at ASC
    """, (machine_id, window_end, window_start))

    candidates = cursor.fetchall()

    if not candidates:
        return None, 0.0

    # Cycle strictement dans un seul OF
    strict_matches = [
        c for c in candidates
        if c["started_at"] <= cycle_time <= (c["ended_at"] or datetime.max.replace(tzinfo=timezone.utc))
    ]

    if len(strict_matches) == 1:
        return strict_matches[0]["id"], 1.0

    if len(strict_matches) > 1:
        # Ambiguité : plusieurs OFs simultanés (chevauchement ERP)
        # → Prendre le plus récent et réduire la confiance
        best = max(strict_matches, key=lambda c: c["started_at"])
        return best["id"], 0.6

    # Aucune correspondance stricte mais candidats dans la fenêtre
    # → Proximité temporelle
    best_candidate = None
    min_distance = timedelta.max

    for c in candidates:
        of_start = c["started_at"]
        of_end = c["ended_at"] or cycle_time + timedelta(minutes=1)
        dist = min(abs((cycle_time - of_start).total_seconds()),
                   abs((cycle_time - of_end).total_seconds()))
        if dist < min_distance.total_seconds():
            min_distance = timedelta(seconds=dist)
            best_candidate = c

    if best_candidate:
        # Confiance décroissante avec la distance (max 30 min → confiance = 0.0)
        distance_s = min_distance.total_seconds()
        confidence = max(0.0, round(1.0 - (distance_s / OVERLAP_WINDOW.total_seconds()), 3))
        return best_candidate["id"], confidence

    return None, 0.0


def resolve_shift_for_cycle(cursor, machine_id: int, cycle_time: datetime, production_order_id: str | None = None) -> int | None:
    """Retourne le shift actif couvrant réellement le cycle."""
    cursor.execute("""
        SELECT id
        FROM shifts
        WHERE machine_id = %s
          AND started_at <= %s
          AND (ended_at IS NULL OR ended_at >= %s)
        ORDER BY
            CASE WHEN production_order_id = %s THEN 0 ELSE 1 END,
            started_at DESC
        LIMIT 1
    """, (machine_id, cycle_time, cycle_time, production_order_id))
    row = cursor.fetchone()
    return row["id"] if row else None


def count_overlapping_production_orders() -> int:
    """Compte les paires d'OF qui se chevauchent sur une même machine."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM production_orders first_order
        JOIN production_orders second_order
          ON second_order.machine_id = first_order.machine_id
         AND second_order.id > first_order.id
         AND first_order.started_at < COALESCE(second_order.ended_at, 'infinity'::timestamptz)
         AND second_order.started_at < COALESCE(first_order.ended_at, 'infinity'::timestamptz)
    """)
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count


def reconcile_existing_cycles() -> int:
    """Rattache les cycles sans OF aux ordres ERP maintenant disponibles."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT time, machine_id
        FROM machine_cycles
        WHERE production_order_id IS NULL
        ORDER BY time, machine_id
    """)
    cycles = cursor.fetchall()

    updated = 0
    for cycle in cycles:
        cycle_time = cycle["time"]
        machine_id = cycle["machine_id"]
        production_order_id, link_confidence = resolve_of_for_cycle(
            cursor,
            machine_id,
            cycle_time,
        )
        
        shift_id = resolve_shift_for_cycle(
            cursor,
            machine_id,
            cycle_time,
            production_order_id,
        )

        cursor.execute("""
            UPDATE machine_cycles
            SET production_order_id = %s,
                shift_id = %s,
                link_confidence = %s
            WHERE time = %s
              AND machine_id = %s
              AND production_order_id IS NULL
        """, (
            production_order_id,
            shift_id,
            link_confidence,
            cycle_time,
            machine_id,
        ))
        updated += cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()
    return updated


def insert_cycles(machine_cycles: list[dict], machine_id: int, passport_id: str):
    """
    Insère les cycles machine dans la base de données avec réconciliation temporelle.
    
    Chaque dict dans machine_cycles doit contenir :
    - time : str ISO 8601 ou None
    - Les champs canoniques (cycle_time_s, dosing_time_s, etc.)
    - raw_data : dict des colonnes non canoniques (optionnel)
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    inserted = 0
    skipped = 0
    quality_issues = []

    for cycle in machine_cycles:
        # Validation du timestamp
        time_val = cycle.get("time")
        if not time_val:
            skipped += 1
            quality_issues.append({
                "issue_type": "missing_timestamp",
                "severity": "warning",
                "description": "Cycle sans horodatage — ignoré"
            })
            continue

        try:
            cycle_time = datetime.fromisoformat(str(time_val))
        except (ValueError, TypeError):
            skipped += 1
            continue

        # Réconciliation temporelle avec l'ERP et résolution du poste (shift)
        production_order_id, link_confidence = resolve_of_for_cycle(
            cursor, machine_id, cycle_time
        )
        
        shift_id = resolve_shift_for_cycle(
            cursor,
            machine_id,
            cycle_time,
            production_order_id,
        )

        # Validation de plausibilité des valeurs (détection d'outliers simples)
        quality_flag = "valid"
        ct = cycle.get("cycle_time_s")
        if ct is not None:
            try:
                ct_f = float(ct)
                if ct_f < 0.5 or ct_f > 3600:
                    quality_flag = "outlier"
                    quality_issues.append({
                        "issue_type": "outlier_value",
                        "severity": "warning",
                        "field_name": "cycle_time_s",
                        "raw_value": str(ct),
                        "description": f"Temps de cycle anormal: {ct_f}s"
                    })
            except (ValueError, TypeError):
                pass

        # Construction de la valeur pour raw_data (JSONB)
        raw_data = cycle.get("raw_data")
        raw_data_json = json.dumps(raw_data) if raw_data else None
        def source_value(name):
            value = cycle.get(name)
            return value if value is not None else (raw_data or {}).get(name)
        scrap_flag = normalize_bool_flag(cycle.get("scrap_flag", False))
        part_quality_status, defect_type = derive_part_quality(raw_data, scrap_flag)
        source_row_hash = cycle.get("source_row_hash") or compute_source_row_hash(cycle)

        # Insertion du cycle
        cursor.execute("""
            INSERT INTO machine_cycles (
                time, machine_id, production_order_id, shift_id, passport_id,
                source_line_no, source_row_hash, cycle_counter,
                cycle_time_s, dosing_time_s, injection_time_s,
                cooling_time_s,
                cushion_mm, switchover_pressure_bar, switchover_position,
                peak_pressure_bar, clamp_force_kn, mold_open_time_s,
                good_parts, scrap_flag,
                barrel_temp_zone1_c, barrel_temp_zone2_c, barrel_temp_zone3_c,
                mold_temperature_c, oil_temperature_c, energy_kwh,
                link_confidence, quality_flag, part_quality_status, defect_type, raw_data
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT DO NOTHING
        """, (
            cycle_time,
            machine_id,
            production_order_id,
            shift_id,
            passport_id,
            cycle.get("source_line_no"),
            source_row_hash,
            cycle.get("cycle_counter"),
                source_value("cycle_time_s"),
                source_value("dosing_time_s"),
                source_value("injection_time_s"),
                source_value("cooling_time_s"),
                source_value("cushion_mm"),
            source_value("switchover_pressure_bar"),
            source_value("switchover_position"),
            source_value("peak_pressure_bar"),
            source_value("clamp_force_kn"),
            source_value("mold_open_time_s"),
            normalize_good_parts(cycle.get("good_parts", cycle.get("good_part", 1))),
            scrap_flag,
            source_value("barrel_temp_zone1_c"),
            source_value("barrel_temp_zone2_c"),
            source_value("barrel_temp_zone3_c"),
            source_value("mold_temperature_c"),
            source_value("oil_temperature_c"),
            source_value("energy_kwh"),
            link_confidence,
            quality_flag,
            part_quality_status,
            defect_type,
            raw_data_json
        ))
        inserted += cursor.rowcount

    conn.commit()

    # Insertion des problèmes de qualité détectés
    if quality_issues:
        for issue in quality_issues:
            cursor.execute("""
                INSERT INTO data_quality_issues (passport_id, issue_type, severity, machine_id, field_name, raw_value, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                passport_id,
                issue.get("issue_type"),
                issue.get("severity", "warning"),
                machine_id,
                issue.get("field_name"),
                issue.get("raw_value"),
                issue.get("description")
            ))
        conn.commit()

    cursor.close()
    conn.close()

    print(f"[RECONCILER] Machine {machine_id}: {inserted} cycles insérés, {skipped} ignorés, {len(quality_issues)} alertes qualité")
    return inserted, skipped


if __name__ == "__main__":
    print("Module de réconciliation IDDRV.")
    print("Importer et appeler insert_cycles(cycles, machine_id, passport_id).")
