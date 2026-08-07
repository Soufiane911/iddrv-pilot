"""
IDDRV — Loader : Lecture et redressement des fichiers machine
=============================================================

Gère la lecture de tous les formats :
1. Fichiers Arburg (tabulaire, avec métadonnées en haut)
2. Fichiers transposés (UTF-16, colonnes = cycles, lignes = paramètres)
3. CSV / XLSX standard ERP/TRS
"""

import csv
import re
import hashlib
import sys
import pandas as pd
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Generator
from zoneinfo import ZoneInfo

try:
    from .profiler import FileProfile, profile_file
    from .mapper import build_column_map, map_row, get_mapping_confidence
except ImportError:  # direct script compatibility
    from profiler import FileProfile, profile_file
    from mapper import build_column_map, map_row, get_mapping_confidence


def compute_file_hash(file_path: str) -> str:
    """Calcule le SHA-256 du fichier (pour le passeport d'import)."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _parse_time_to_datetime(time_str: str, ref_date: date = None) -> datetime | None:
    """
    Convertit une heure (HH:MM ou HH:MM:SS) en datetime.
    Si l'heure est inférieure à l'heure précédente, on incrémente la date (passage minuit).
    """
    ref_date = ref_date or date.today()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(time_str.strip(), fmt).time()
            return datetime.combine(ref_date, t)
        except ValueError:
            continue
    return None


def _normalize_datetime_utc(value: datetime) -> datetime:
    """Retourne un horodatage explicite en UTC pour les sources sans timezone."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_source_datetime(value) -> datetime | None:
    """Convertit les formats date/heure courants des exports machine/ERP."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is None else value.astimezone(timezone.utc)
    if hasattr(value, "to_pydatetime"):
        parsed = value.to_pydatetime()
        return parsed if parsed.tzinfo is None else parsed.astimezone(timezone.utc)

    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat"}:
        return None

    if re.fullmatch(r"\d{10}(?:\.\d+)?", text):
        try:
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    iso_text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_text)
        return parsed if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d.%m.%y %H:%M:%S",
        "%d.%m.%y %H:%M",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _extract_metadata_datetime(metadata_lines: list[str]) -> datetime | None:
    """Extrait une date complète depuis les métadonnées machine."""
    for meta_line in metadata_lines:
        value = re.split(r"[;:]", meta_line, maxsplit=1)[-1].strip()
        parsed = _parse_source_datetime(value)
        if parsed:
            return parsed
    return None


def _find_timestamp_column(headers: list[str]) -> str | None:
    """Retourne la colonne source la plus probable pour l'horodatage."""
    normalized = {h.lower().strip(): h for h in headers}
    for candidate in ("timestamp", "time", "datetime", "date_time", "dateheure", "date heure"):
        if candidate in normalized:
            return normalized[candidate]

    for h in headers:
        lh = h.lower().strip()
        if "timestamp" in lh or "datetime" in lh or "date heure" in lh:
            return h
    return None


def _decimal_fraction_to_time(fraction: str, ref_date: date = None) -> datetime | None:
    """
    Convertit une fraction de journée (ex: 0.488518519 = 11:43:28) en datetime.
    Format utilisé par certains exports machine Excel/CSV.
    """
    ref_date = ref_date or date.today()
    try:
        val = float(fraction.replace(",", "."))
        seconds = int(val * 86400)
        return datetime.combine(ref_date, datetime.min.time()) + timedelta(seconds=seconds)
    except (ValueError, TypeError):
        return None


def read_arburg_protocol(profile: FileProfile, mapping_builder=build_column_map) -> list[dict]:
    """
    Lit un fichier protocole Arburg (format tabulaire avec métadonnées en haut).
    Structure attendue :
      - Lignes 0..N   : métadonnées clé-valeur
      - Ligne N+1     : noms de colonnes (t4015, t4012, ...)
      - Ligne N+2     : unités (s, bar, cm³, ...)
      - Ligne N+3+    : données numériques
    """
    rows = []
    with open(profile.file_path, encoding=profile.encoding, errors="replace") as f:
        lines = f.readlines()

    # En-têtes et unités
    header_line = lines[profile.header_row_index].rstrip()
    headers = [h.strip() for h in header_line.split(profile.delimiter) if h.strip()]

    unit_line = None
    if profile.unit_row_index is not None and profile.unit_row_index < len(lines):
        unit_line = lines[profile.unit_row_index].rstrip()

    # Extraction de la date depuis les métadonnées si disponible
    metadata_dt = _extract_metadata_datetime(profile.metadata_lines)
    ref_date = metadata_dt.date() if metadata_dt else date.today()

    # Extraction du machine_id depuis les métadonnées si disponible
    machine_id_meta = None
    for line in profile.metadata_lines:
        if "machine" in line.lower() or "presse" in line.lower():
            if ":" in line:
                machine_id_meta = line.split(":", 1)[1].strip()
            elif "=" in line:
                machine_id_meta = line.split("=", 1)[1].strip()
            elif ";" in line:
                machine_id_meta = line.split(";", 1)[1].strip()

    # Construction du mapping de colonnes
    col_map = mapping_builder(headers, brand=profile.brand_detected)

    # Lecture des lignes de données
    current_date = ref_date
    prev_time = None

    for i in range(profile.data_start_row, len(lines)):
        line = lines[i].rstrip()
        if not line.strip():
            continue

        values = line.split(profile.delimiter)
        # Compléter ou tronquer à la taille des en-têtes
        while len(values) < len(headers):
            values.append("")
        raw_row = dict(zip(headers, values[:len(headers)]))

        canonical = map_row(raw_row, col_map)

        # Gestion du timestamp : chercher une colonne heure (t007 chez Arburg)
        time_col = None
        for h in headers:
            if "007" in h.lower() or "heure" in h.lower() or "time" in h.lower():
                time_col = h
                break

        if time_col and raw_row.get(time_col, "").strip():
            time_str = raw_row[time_col].strip()
            parsed_time = None
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    parsed_time = datetime.strptime(time_str, fmt).time()
                    break
                except ValueError:
                    continue

            if parsed_time:
                # Si le temps recule par rapport au précédent, passage à minuit
                if prev_time and parsed_time < prev_time:
                    current_date += timedelta(days=1)
                prev_time = parsed_time
                ts = datetime.combine(current_date, parsed_time)
                canonical["time"] = ts.isoformat()

        if machine_id_meta and ("machine_id" not in canonical or not canonical["machine_id"]):
            canonical["machine_id"] = machine_id_meta

        rows.append(canonical)

    return rows, col_map


def read_transposed_file(profile: FileProfile, mapping_builder=build_column_map) -> list[dict]:
    """
    Lit un fichier transposé (ex: data février tubes.txt en UTF-16).
    Chaque ligne = un paramètre, chaque colonne = un cycle.
    
    Structure :
      - Ligne 0 : dates (répétées) ou "Column1", "Column2"...
      - Ligne 1 : timestamps sous forme de fraction décimale de journée
      - Ligne 2 : numéros de cycles
      - Lignes 3+ : valeurs des paramètres (cycle_time, dosing_time, etc.)
    """
    rows = []
    with open(profile.file_path, encoding=profile.encoding, errors="replace") as f:
        raw_lines = [l.rstrip("\n\r") for l in f.readlines()]

    if not raw_lines:
        return [], {}

    delimiter = profile.delimiter

    # Identifier les lignes (nom de paramètre, valeurs)
    param_names = []
    data_matrix = []  # data_matrix[param_idx][cycle_idx] = value

    for line_idx, line in enumerate(raw_lines):
        parts = line.split(delimiter)
        if not parts:
            continue
        param_names.append(parts[0].strip())
        data_matrix.append([p.strip() for p in parts[1:]])

    if not data_matrix:
        return [], {}

    num_cycles = max(len(row) for row in data_matrix)

    # Détecter les lignes spéciales
    # Ligne 0 : dates (ex: "11.02.26" ou "Column1")
    # Ligne 1 : fractions de journée (ex: 0,488518519)
    # Ligne 2 : numéros de cycles (ex: 824, 823, ...)
    # Lignes suivantes : valeurs de paramètres

    date_row_idx = 0
    time_row_idx = 1
    cycle_num_row_idx = 2
    param_start_idx = 3

    # Extraction des dates de référence (première valeur non-vide de la ligne 0)
    ref_date = date.today()
    if date_row_idx < len(data_matrix):
        for val in data_matrix[date_row_idx]:
            date_match = re.search(r'(\d{2})[.\-/](\d{2})[.\-/](\d{2,4})', val)
            if date_match:
                d, m, y = date_match.groups()
                year = int(y) if len(y) == 4 else 2000 + int(y)
                try:
                    ref_date = date(year, int(m), int(d))
                except ValueError:
                    pass
                break

    # Extraction des timestamps (ligne 1 = fractions de journée)
    timestamps = []
    if time_row_idx < len(data_matrix):
        for frac_str in data_matrix[time_row_idx]:
            ts = _decimal_fraction_to_time(frac_str, ref_date)
            timestamps.append(ts)

    # Extraction des numéros de cycles (ligne 2)
    cycle_numbers = []
    if cycle_num_row_idx < len(data_matrix):
        for val in data_matrix[cycle_num_row_idx]:
            try:
                cycle_numbers.append(int(val))
            except (ValueError, TypeError):
                cycle_numbers.append(None)

    # Construire les noms de paramètres réels (lignes 3+)
    real_param_names = param_names[param_start_idx:]

    # Construire le mapping de colonnes sur les noms de paramètres
    col_map = mapping_builder(real_param_names, brand=profile.brand_detected)

    # Assembler les cycles
    for cycle_idx in range(num_cycles):
        raw_row = {}
        for param_i, param_name in enumerate(real_param_names):
            actual_row_idx = param_start_idx + param_i
            if actual_row_idx < len(data_matrix) and cycle_idx < len(data_matrix[actual_row_idx]):
                raw_row[param_name] = data_matrix[actual_row_idx][cycle_idx]

        canonical = map_row(raw_row, col_map)

        # Ajouter le timestamp
        ts = timestamps[cycle_idx] if cycle_idx < len(timestamps) else None
        canonical["time"] = ts.isoformat() if ts else None

        # Ajouter le numéro de cycle
        cn = cycle_numbers[cycle_idx] if cycle_idx < len(cycle_numbers) else None
        if cn and "cycle_counter" not in canonical:
            canonical["cycle_counter"] = cn

        rows.append(canonical)

    return rows, col_map


def read_erp_trs_xlsx(file_path: str, sheet_name: str = "Données_Audit") -> list[dict]:
    """
    Lit un fichier ERP/TRS Excel et retourne les lignes d'ordres de fabrication.
    """
    try:
        xl = pd.ExcelFile(file_path)
        sheets = xl.sheet_names
        if sheet_name not in sheets:
            if len(sheets) > 0:
                sheet_name = sheets[0]
        df = pd.read_excel(xl, sheet_name=sheet_name)
    except Exception as e:
        print(f"[ERREUR] Impossible de lire {file_path}: {e}")
        return []

    orders = []
    for _, row in df.iterrows():
        order = {}

        # Mapping des colonnes ERP standard (supporte français et anglais)
        field_map = {
            "Réf OF": "id",
            "production_order_id": "id",
            "Réf. Machine": "machine_erp_ref",
            "machine_erp_ref": "machine_erp_ref",
            "Lib. Machine": "machine_name",
            "machine_name": "machine_name",
            "Début Equipe": "started_at",
            "started_at": "started_at",
            "Fin Equipe": "ended_at",
            "ended_at": "ended_at",
            "Num Equipe": "shift_number",
            "shift_number": "shift_number",
            "Réf. produit": "product_ref",
            "product_ref": "product_ref",
            "Lib. Produit": "product_name",
            "product_name": "product_name",
            "Réf. outil": "tool_ref",
            "tool_ref": "tool_ref",
            "Réf. Matière": "material_ref",
            "material_ref": "material_ref",
            "Qté Pieces Bonnes": "erp_good_parts",
            "good_parts": "erp_good_parts",
            "Total Rebuts": "erp_scrap_count",
            "scrap_count": "erp_scrap_count",
            "T.R.S.": "erp_trs",
            "expected_trs": "erp_trs",
            "Tps Disponible (h)": "erp_available_time_h",
            "planned_runtime_h": "erp_available_time_h",
            "Tps Fct Brut (h)": "erp_running_time_h",
            "Cycle Moyen": "erp_cycle_time_s",
            "theoretical_cycle_time_s": "erp_cycle_time_s",
            "Nb Cycles": "nb_cycles",
        }

        for src_col, dst_col in field_map.items():
            val = row.get(src_col)
            if pd.notna(val):
                if dst_col in ("started_at", "ended_at"):
                    val = _parse_source_datetime(val)
                order[dst_col] = val

        if order.get("id") and order.get("machine_erp_ref"):
            orders.append(order)

    return orders


def load_file(
    file_path: str,
    *,
    site_id: int | str | None = None,
    machine_erp_ref: str | None = None,
    parser_version: str = "arburg-selogica-gestica-v1",
    source_timezone: str | None = None,
) -> tuple[list[dict], FileProfile, dict]:
    """
    Point d'entrée principal du loader.
    Profile le fichier puis le lit avec le bon lecteur.
    
    Retourne (lignes_canoniques, profil, mapping_colonnes).
    """
    profile = profile_file(file_path)
    mapping_builder = build_column_map
    if site_id is not None or machine_erp_ref is not None:
        from .mappers.versioned import build_versioned_column_map

        def mapping_builder(headers, *, brand="generic"):
            column_map, _ = build_versioned_column_map(
                headers,
                brand=brand,
                site_id=site_id,
                machine_erp_ref=machine_erp_ref,
                parser_version=parser_version,
            )
            return column_map

    if profile.is_transposed:
        rows, col_map = read_transposed_file(profile, mapping_builder=mapping_builder)
    elif profile.brand_detected == "arburg" or profile.metadata_lines:
        rows, col_map = read_arburg_protocol(profile, mapping_builder=mapping_builder)
    else:
        # Fichier CSV/XLSX générique
        try:
            ext = Path(file_path).suffix.lower()
            if ext in (".xlsx", ".xls"):
                df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path, sep=profile.delimiter,
                                 encoding=profile.encoding, decimal=",")
            headers = df.columns.tolist()
            col_map = mapping_builder(headers, brand=profile.brand_detected)
            timestamp_col = _find_timestamp_column([str(h) for h in headers])
            rows = []
            for _, row_data in df.iterrows():
                raw_row = {str(k): str(v) for k, v in row_data.items()}
                canonical = map_row(raw_row, col_map)
                ts = _parse_source_datetime(raw_row.get(timestamp_col)) if timestamp_col else None
                canonical["time"] = ts.isoformat() if ts else None
                rows.append(canonical)
        except Exception as e:
            print(f"[ERREUR] {e}")
            rows, col_map = [], {}

    timezone_value = ZoneInfo(source_timezone) if source_timezone else timezone.utc
    for row in rows:
        value = row.get("time")
        if not value:
            continue
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone_value)
        row["time"] = parsed.astimezone(timezone.utc).isoformat()

    print(f"[LOADER] {Path(file_path).name} → {len(rows)} cycles chargés "
          f"(brand: {profile.brand_detected}, transposé: {profile.is_transposed})", file=sys.stderr)

    return rows, profile, col_map


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python loader.py <fichier>")
        sys.exit(1)

    file_path = sys.argv[1]
    rows, profile, col_map = load_file(file_path)

    print(f"\n=== RÉSULTAT ===")
    print(f"  Lignes chargées : {len(rows)}")
    print(f"  Confiance mapping: {get_mapping_confidence(col_map):.0%}")
    if rows:
        print(f"  Exemple ligne 0 : {rows[0]}")
