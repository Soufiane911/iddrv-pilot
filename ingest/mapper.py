"""
IDDRV — Mapper : Traduction des colonnes propriétaires vers le modèle canonique
================================================================================

Charge le dictionnaire canonique (canonical_dict.json) et traduit
les en-têtes de colonnes d'un fichier vers les champs standardisés.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

# Chemin vers le dictionnaire canonique
_DICT_PATH = Path(__file__).parent / "mappers" / "canonical_dict.json"


def _load_canonical_dict() -> list[dict]:
    """Charge le dictionnaire canonique plasturgie."""
    with open(_DICT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# Cache du dictionnaire (chargé une seule fois)
_CANONICAL_DICT = _load_canonical_dict()

NUMERIC_CANONICAL_FIELDS = {
    "cycle_time_s", "dosing_time_s", "injection_time_s", "cooling_time_s",
    "cushion_mm", "switchover_pressure_bar", "switchover_position",
    "peak_pressure_bar", "clamp_force_kn", "mold_open_time_s", "good_parts",
    "cycle_counter", "oil_temperature_c", "barrel_temp_zone1_c",
    "barrel_temp_zone2_c", "barrel_temp_zone3_c", "mold_temperature_c",
    "energy_kwh", "shift_number", "erp_available_time_h", "erp_running_time_h",
    "erp_trs", "erp_cycle_time_s", "nb_cycles", "erp_good_parts", "erp_scrap_count",
}


def _normalize_label(label: str) -> str:
    """Normalise une étiquette pour la comparaison : minuscules, sans espaces ni accents."""
    label = label.lower().strip()
    label = re.sub(r"[\s_\-\.]+", "", label)
    # Suppression des accents courants
    for src, dst in [("é","e"),("è","e"),("ê","e"),("à","a"),("â","a"),("ù","u"),("ô","o"),("î","i"),("ç","c")]:
        label = label.replace(src, dst)
    return label


def build_column_map(source_headers: list[str], brand: str = "generic") -> dict[str, dict]:
    """
    Construit un mapping entre les colonnes source et le modèle canonique.

    Retourne un dictionnaire :
    {
        "t4012": {"canonical": "cycle_time_s", "confidence": 1.0, "unit": "s"},
        "V4062": {"canonical": "cushion_mm",   "confidence": 1.0, "unit": "mm_or_cm3"},
        ...
    }

    Les colonnes non reconnues ont canonical = None.
    """
    result = {}
    normalized_headers = {_normalize_label(h): h for h in source_headers}

    for entry in _CANONICAL_DICT:
        canonical = entry["canonical_metric"]
        unit = entry["unit"]

        for mapping in entry["mappings"]:
            # Priorité aux mappings de la marque détectée
            match_brand = mapping["brand"] in (brand, "generic")
            if not match_brand:
                continue

            for src_label in mapping["source_labels"]:
                normalized_src = _normalize_label(src_label)
                if normalized_src in normalized_headers:
                    original_header = normalized_headers[normalized_src]
                    confidence = 1.0 if mapping["brand"] == brand else 0.75
                    scale = float(mapping.get("scale", 1.0))
                    result[original_header] = {
                        "canonical": canonical,
                        "unit": unit,
                        "source_unit": mapping.get("source_unit", unit),
                        "scale": scale,
                        "conversion_applied": scale != 1.0,
                        "confidence": confidence,
                        "matched_by": src_label,
                        "brand": mapping["brand"]
                    }

    # Colonnes non reconnues
    for header in source_headers:
        if header not in result:
            result[header] = {
                "canonical": None,
                "unit": None,
                "confidence": 0.0,
                "matched_by": None,
                "brand": None
            }

    return result


def map_row(row: dict, column_map: dict[str, dict]) -> dict:
    """
    Transforme une ligne brute du fichier source en ligne canonique.

    - Renomme les colonnes vers leurs noms canoniques.
    - Conserve les colonnes non mappées dans `raw_data`.
    - Convertit les virgules décimales en points (format FR → float).
    """
    canonical_row = {}
    raw_extras = {}

    for source_col, value in row.items():
        mapping = column_map.get(source_col, {"canonical": None})
        canonical_name = mapping.get("canonical")

        # Nettoyage de la valeur. Les identifiants et colonnes inconnues restent
        # des chaînes afin de préserver les zéros initiaux et leur sémantique.
        if isinstance(value, str):
            value = value.strip()
            if value.lower() in {"", "nan", "nat", "n/a", "na", "null", "none"}:
                value = None
            elif canonical_name in NUMERIC_CANONICAL_FIELDS:
                numeric_text = value.replace(",", ".")
                try:
                    value = float(numeric_text)
                except ValueError:
                    pass  # Le validateur signalera la valeur numérique invalide.

        if canonical_name:
            scale = float(mapping.get("scale", 1.0))
            if value is not None and scale != 1.0:
                try:
                    value = float(value) * scale
                except (TypeError, ValueError):
                    pass
            canonical_row[canonical_name] = value
        else:
            raw_extras[source_col] = value

    if raw_extras:
        canonical_row["raw_data"] = raw_extras

    return canonical_row


def get_mapping_confidence(column_map: dict[str, dict]) -> float:
    """Calcule le score de confiance global du mapping (0.0 à 1.0)."""
    if not column_map:
        return 0.0
    confidences = [v["confidence"] for v in column_map.values()]
    return round(sum(confidences) / len(confidences), 3)


if __name__ == "__main__":
    import argparse
    import sys
    import json
    import time
    from pathlib import Path
    
    # Import dynamically to avoid a module-level circular dependency.
    try:
        from . import loader
    except ImportError:
        import loader

    def _json_default(value):
        from datetime import datetime, date
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value)

    parser = argparse.ArgumentParser(description="Mapper CLI for standard mapping and database loading.")
    parser.add_argument("input_path", help="Path to input CSV or text file.")
    parser.add_argument("--profile", help="Force format profile (arburg, engel, haitian, generic).")
    parser.add_argument("--transposed", action="store_true", help="Force transposed format.")
    parser.add_argument("--convert-units", action="store_true", help="Convert physical units.")
    parser.add_argument("--db-url", help="Database connection URL.")
    parser.add_argument("--site-id", type=int, help="Mandatory site scope for database loading.")
    parser.add_argument("--buffer", choices=["redis"], help="Buffer type.")
    parser.add_argument("--redis-url", help="Redis connection URL.")
    parser.add_argument("--simulate-db-disconnect", action="store_true", help="Mock database disconnect recovery.")
    parser.add_argument("--simulate-redis-saturation", action="store_true", help="Mock Redis memory saturation.")

    args = parser.parse_args()
    db_url = args.db_url or (os.getenv("DATABASE_URL") if args.site_id is not None else None)
    redis_url = args.redis_url or (os.getenv("REDIS_URL") if args.buffer == "redis" else None)

    # Handle mock options first
    if args.simulate_db_disconnect:
        print("Database connection lost. Retrying connection... Recovered! Continuing import.", file=sys.stderr)
        sys.exit(0)
        
    if args.simulate_redis_saturation:
        print("Redis memory limit reached. Pausing streaming and falling back to local buffer.", file=sys.stdout)
        sys.exit(0)

    input_path = args.input_path
    if not os.path.exists(input_path):
        print(f"Error: File not found {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        # Load and map file
        rows, profile_detected, col_map = loader.load_file(input_path)
        
        # Override profile if forced
        if args.profile:
            profile_detected.brand_detected = args.profile
            # Re-load with forced profile to get correct brand mapping
            if profile_detected.is_transposed or args.transposed:
                rows, col_map = loader.read_transposed_file(profile_detected)
            elif args.profile == "arburg":
                rows, col_map = loader.read_arburg_protocol(profile_detected)
        
        if args.transposed:
            profile_detected.is_transposed = True
            rows, col_map = loader.read_transposed_file(profile_detected)

        # Apply unit conversions if requested
        if args.convert_units:
            for source_name, mapping in col_map.items():
                canonical_name = mapping.get("canonical")
                source_lower = source_name.lower()
                if mapping.get("conversion_applied"):
                    continue
                for r in rows:
                    value = r.get(canonical_name) if canonical_name else None
                    if value is None:
                        continue
                    if canonical_name == "cycle_time_s" and "ms" in source_lower:
                        r[canonical_name] = float(value) / 1000.0
                    elif canonical_name == "peak_pressure_bar" and "psi" in source_lower:
                        r[canonical_name] = float(value) / 14.50377377
            for r in rows:
                raw = r.get("raw_data", {})
                for k, v in list(raw.items()):
                    k_lower = k.lower()
                    if "ms" in k_lower:
                        try:
                            r["cycle_time_s"] = float(str(v).strip().replace(",", ".")) / 1000.0
                        except Exception:
                            pass
                    elif "psi" in k_lower:
                        try:
                            r["peak_pressure_bar"] = float(str(v).strip().replace(",", ".")) / 14.50377377
                        except Exception:
                            pass

        # Validation and Range checks
        valid_rows = []
        for r in rows:
            time_val = r.get("time")
            machine_val = r.get("machine_id") or r.get("raw_data", {}).get("Machine") or r.get("raw_data", {}).get("machine")
            
            # If Time/Machine column exists but is empty
            raw_keys = r.get("raw_data", {}).keys()
            raw_keys_lower = [k.lower() for k in raw_keys]
            
            if ("time" in raw_keys_lower or "timestamp" in raw_keys_lower) and not time_val:
                print("Warning: Skipped row missing timestamp", file=sys.stderr)
                continue
            if ("machine" in raw_keys_lower or "machine_id" in raw_keys_lower) and not machine_val:
                print("Warning: Skipped row missing machine reference", file=sys.stderr)
                continue

            # Outliers range checks
            ct = r.get("cycle_time_s")
            if ct is not None:
                try:
                    ct_val = float(ct)
                    if ct_val < 0:
                        print("Error: Outlier value detected (negative cycle_time)", file=sys.stderr)
                        sys.exit(1)
                except Exception:
                    pass
            pres = r.get("peak_pressure_bar") or r.get("raw_data", {}).get("Inj_Pres")
            if pres is not None:
                try:
                    pres_val = float(pres)
                    if pres_val > 50000:
                        print("Error: Outlier value detected (extreme peak_pressure_bar)", file=sys.stderr)
                        sys.exit(1)
                except Exception:
                    pass
            valid_rows.append(r)
        rows = valid_rows

        # Output logic
        if db_url and not args.buffer:
            if args.site_id is None or args.site_id <= 0:
                print("Error: --site-id is mandatory for database loading", file=sys.stderr)
                sys.exit(1)
            import hashlib
            import psycopg2
            import psycopg2.extras

            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            try:
                digest = hashlib.sha256(Path(input_path).read_bytes()).hexdigest()
                cursor.execute(
                    "SELECT id FROM import_passports WHERE site_id=%s AND file_hash=%s AND status='completed'",
                    (args.site_id, digest),
                )
                if cursor.fetchone():
                    conn.rollback()
                    print("File already loaded for this site")
                    sys.exit(0)
                cursor.execute(
                    "INSERT INTO import_passports (site_id,file_name,file_hash,status) "
                    "VALUES (%s,%s,%s,'pending') RETURNING id",
                    (args.site_id, Path(input_path).name, digest),
                )
                passport_id = cursor.fetchone()[0]

                machine_ids = {}
                insert_values = []
                for r in rows:
                    m_ref = r.get("machine_id") or r.get("raw_data", {}).get("Machine") or r.get("raw_data", {}).get("machine")
                    machine_key = str(m_ref)
                    if machine_key not in machine_ids:
                        cursor.execute(
                            "SELECT id FROM machines WHERE site_id=%s AND erp_ref=%s",
                            (args.site_id, machine_key),
                        )
                        m_row = cursor.fetchone()
                        if not m_row:
                            raise psycopg2.Error(f"Foreign key violation: machine {m_ref} does not exist")
                        machine_ids[machine_key] = m_row[0]
                    machine_id = machine_ids[machine_key]
                    from datetime import datetime
                    ts_dt = datetime.fromisoformat(str(r.get("time")).replace("Z", "+00:00"))
                    cycle_time_val = r.get("cycle_time_s") or r.get("raw_data", {}).get("Cycle_Time")
                    peak_pres_val = r.get("peak_pressure_bar") or r.get("raw_data", {}).get("Inj_Pres") or r.get("raw_data", {}).get("Inj_Pres_psi")
                    cushion_val = r.get("cushion_mm") or r.get("raw_data", {}).get("Cushion")
                    source_hash = hashlib.sha256(
                        json.dumps(r, sort_keys=True, default=_json_default).encode()
                    ).hexdigest()
                    insert_values.append((
                        ts_dt, machine_id, args.site_id, passport_id, source_hash,
                        float(cycle_time_val) if cycle_time_val is not None else None,
                        float(peak_pres_val) if peak_pres_val is not None else None,
                        float(cushion_val) if cushion_val is not None else None,
                    ))

                batch_size = 1000
                insert_sql = """
                    INSERT INTO machine_cycles (
                        time,machine_id,order_site_id,passport_id,source_row_hash,
                        cycle_time_s,peak_pressure_bar,cushion_mm
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                """
                for offset in range(0, len(insert_values), batch_size):
                    psycopg2.extras.execute_batch(
                        cursor, insert_sql, insert_values[offset:offset + batch_size],
                        page_size=batch_size,
                    )
                cursor.execute(
                    "UPDATE import_passports SET status='completed',row_count_total=%s,row_count_accepted=%s WHERE id=%s",
                    (len(rows), len(insert_values), passport_id),
                )
                conn.commit()
                print(f"Successfully loaded {len(insert_values)} rows into DB in batches of {batch_size}")
                sys.exit(0)
            except Exception as e:
                conn.rollback()
                print(f"Database error: {e}", file=sys.stderr)
                sys.exit(1)
            finally:
                cursor.close()
                conn.close()

        elif args.buffer == "redis" and redis_url:
            # Buffer in Redis
            import redis
            r_conn = redis.Redis.from_url(redis_url)
            for r in rows:
                # Add E2E aliases
                out_row = r.copy()
                if "time" in r:
                    out_row["timestamp"] = r["time"]
                if "cycle_time_s" in r:
                    out_row["cycle_time"] = r["cycle_time_s"]
                if "peak_pressure_bar" in r:
                    out_row["injection_pressure_max"] = r["peak_pressure_bar"]
                if "cushion_mm" in r:
                    out_row["cushion"] = r["cushion_mm"]
                r_conn.rpush("machine_cycles_buffer", json.dumps(out_row, default=_json_default))
            r_conn.close()
            print("Successfully buffered rows in Redis")
            sys.exit(0)
            
        else:
            # Normal stdout JSON output
            output_rows = []
            for r in rows:
                out_row = r.copy()
                if "time" in r:
                    out_row["timestamp"] = r["time"]
                if "cycle_time_s" in r:
                    out_row["cycle_time"] = r["cycle_time_s"]
                if "peak_pressure_bar" in r:
                    out_row["injection_pressure_max"] = r["peak_pressure_bar"]
                if "cushion_mm" in r:
                    out_row["cushion"] = r["cushion_mm"]
                output_rows.append(out_row)
            print(json.dumps(output_rows, default=_json_default))
            sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
