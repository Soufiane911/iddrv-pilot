"""
IDDRV — Profiler dynamique de formats de fichiers machine
=========================================================

Détecte automatiquement :
- L'encodage (UTF-8, UTF-16 LE/BE, Latin-1)
- Le délimiteur (virgule, point-virgule, tabulation, espace)
- L'orientation (normalisée vs transposée)
- Le type de constructeur (Arburg, Engel, Haitian, générique)
- La ligne d'en-tête réelle (certains fichiers ont des métadonnées en tête)
"""

import re
import csv
import chardet
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

ARBURG_SIGNATURES = [
    "protocole arburg", "arburg protokoll", "arburg protocol",
    "t4012", "t4015", "v4062", "f1403", "f077"
]

ENGEL_SIGNATURES = [
    "engel", "t_cycle", "t_dos", "ActivePlastificationTime", "CC300"
]

HAITIAN_SIGNATURES = [
    "haitian", "CycleTime", "DosingTime", "CushionVolume"
]


@dataclass
class FileProfile:
    """Passeport de format d'un fichier machine."""
    file_path: str
    encoding: str = "utf-8"
    encoding_confidence: float = 1.0
    delimiter: str = ";"
    is_transposed: bool = False
    header_row_index: int = 0
    unit_row_index: Optional[int] = None
    data_start_row: int = 1
    brand_detected: str = "generic"
    brand_confidence: float = 0.0
    column_count: int = 0
    row_count: int = 0
    metadata_lines: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def detect_encoding(file_path: str) -> tuple[str, float]:
    """Détecte l'encodage du fichier avec chardet."""
    with open(file_path, "rb") as f:
        raw = f.read(8192)
    result = chardet.detect(raw)
    encoding = result.get("encoding") or "utf-8"
    confidence = result.get("confidence") or 0.5

    # Normalisation des encodages courants
    encoding_map = {
        "utf-16-le": "utf-16",
        "utf-16-be": "utf-16",
        "ascii": "utf-8",
        "iso-8859-1": "latin-1",
        "windows-1252": "latin-1",
    }
    encoding = encoding_map.get(encoding.lower(), encoding.lower())
    return encoding, confidence


def detect_delimiter(sample_lines: list[str]) -> str:
    """Détecte le délimiteur dominant dans un échantillon de lignes."""
    candidates = {";": 0, ",": 0, "\t": 0, " ": 0}
    lines = sample_lines[:20]
    repeated_counts = {}
    for line in lines:
        for delim in candidates:
            candidates[delim] += line.count(delim)
    for delim in candidates:
        repeated_counts[delim] = sum(line.count(delim) >= 2 for line in lines)

    # Metadata contains spaces, while the tabular section repeats its delimiter
    # several times on consecutive rows. Prefer that signal when available.
    best_repeated = max(repeated_counts, key=repeated_counts.get)
    if repeated_counts[best_repeated] > 0:
        return best_repeated
    return max(candidates, key=candidates.get)


def is_transposed(lines: list[str], delimiter: str) -> bool:
    """
    Détecte si le fichier est transposé.
    Un fichier transposé a les paramètres en lignes et les cycles en colonnes.
    Heuristique : si beaucoup plus de colonnes que de lignes → transposé.
    """
    if not lines:
        return False

    # Some compact exports explicitly put the metric names in the first column.
    # They are transposed even when the file is too small for the wide-matrix
    # heuristic below.
    first_column = [line.split(delimiter, 1)[0].strip().lower() for line in lines if line.strip()]
    transposed_headers = {"variable", "parameter", "parametre", "paramètre"}
    timestamp_labels = {"time", "timestamp", "date_time", "dateheure", "date heure"}
    if (
        len(first_column) >= 3
        and first_column[0] in transposed_headers
        and any(label in timestamp_labels for label in first_column[1:])
    ):
        return True

    col_counts = [len(line.split(delimiter)) for line in lines[:20] if line.strip()]
    avg_cols = sum(col_counts) / max(len(col_counts), 1)
    row_count = len([l for l in lines if l.strip()])
    return avg_cols > row_count * 2 and avg_cols > 30


def detect_brand(lines: list[str]) -> tuple[str, float]:
    """Détecte le constructeur de la machine à partir du contenu du fichier."""
    content = "\n".join(lines[:30]).lower()

    arburg_score = sum(1 for sig in ARBURG_SIGNATURES if sig.lower() in content)
    engel_score = sum(1 for sig in ENGEL_SIGNATURES if sig.lower() in content)
    haitian_score = sum(1 for sig in HAITIAN_SIGNATURES if sig.lower() in content)

    scores = {"arburg": arburg_score, "engel": engel_score, "haitian": haitian_score}
    best_brand = max(scores, key=scores.get)
    best_score = scores[best_brand]

    if best_score == 0:
        return "generic", 0.0

    confidence = min(best_score / 4.0, 1.0)
    return best_brand, round(confidence, 2)


def find_header_row(lines: list[str], delimiter: str) -> tuple[int, Optional[int], int]:
    """
    Cherche la ligne d'en-tête réelle et la ligne d'unités.
    Retourne (header_row_index, unit_row_index, data_start_row).

    Dans les fichiers Arburg par exemple :
    - Lignes 0-15 : métadonnées (Moule, Machine, Année, etc.)
    - Ligne 16 : noms de colonnes (t4015, t4012, ...)
    - Ligne 17 : unités (s, s, bar, cm³, ...)
    - Ligne 18+ : données numériques
    """
    for i, line in enumerate(lines):
        cols = [c.strip() for c in line.split(delimiter) if c.strip()]
        if len(cols) < 3:
            continue
        numeric_count = sum(1 for c in cols if re.match(r'^[\d.,+-]+$', c))
        alpha_count = sum(1 for c in cols if re.match(r'^[a-zA-Z]', c))

        # Ligne d'en-tête probable : beaucoup de tokens alpha
        if alpha_count > len(cols) * 0.4 and alpha_count > 2:
            # Vérifier si la ligne suivante contient des unités
            unit_row = None
            if i + 1 < len(lines):
                next_cols = [c.strip() for c in lines[i + 1].split(delimiter) if c.strip()]
                unit_patterns = ["s", "bar", "cm³", "mm", "°c", "kn", "h:min", "°C"]
                unit_count = sum(1 for c in next_cols if c.lower() in unit_patterns)
                if unit_count > 1:
                    unit_row = i + 1

            data_start = (unit_row + 1) if unit_row is not None else i + 1
            return i, unit_row, data_start

    return 0, None, 1


def profile_file(file_path: str) -> FileProfile:
    """
    Point d'entrée principal : profile un fichier machine et retourne
    une description complète de sa structure.
    """
    path = Path(file_path)
    profile = FileProfile(file_path=file_path)

    # 1. Détection de l'encodage
    profile.encoding, profile.encoding_confidence = detect_encoding(file_path)

    # 2. Lecture des premières lignes
    try:
        with open(file_path, encoding=profile.encoding, errors="replace") as f:
            raw_lines = f.readlines()
    except Exception as e:
        profile.notes.append(f"Erreur de lecture: {e}")
        return profile

    lines = [l.rstrip("\n\r") for l in raw_lines]
    profile.row_count = len(lines)

    # 3. Détection du délimiteur
    profile.delimiter = detect_delimiter(lines)

    # 4. Détection transposé/normal
    profile.is_transposed = is_transposed(lines, profile.delimiter)

    if profile.is_transposed:
        profile.notes.append("Fichier transposé détecté : paramètres en lignes, cycles en colonnes.")
        profile.header_row_index = 0
        profile.data_start_row = 1
        profile.column_count = len(lines)  # Chaque ligne = un paramètre
    else:
        # 5. Détection de la ligne d'en-tête et de données
        profile.header_row_index, profile.unit_row_index, profile.data_start_row = \
            find_header_row(lines, profile.delimiter)

        # Stocker les lignes de métadonnées avant l'en-tête
        profile.metadata_lines = lines[:profile.header_row_index]

        # Calculer le nombre de colonnes depuis la ligne d'en-tête
        if profile.header_row_index < len(lines):
            profile.column_count = len(
                [c for c in lines[profile.header_row_index].split(profile.delimiter) if c.strip()]
            )

    # 6. Détection du constructeur
    profile.brand_detected, profile.brand_confidence = detect_brand(lines)

    return profile


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python profiler.py <chemin_vers_fichier>"}), file=sys.stderr)
        sys.exit(1)

    fp = sys.argv[1]
    
    # 1. Détection de fichier binaire
    try:
        with open(fp, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                print("Error: Binary file detected", file=sys.stderr)
                sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        p = profile_file(fp)

        if p.row_count == 0:
            print("Error: Empty input file", file=sys.stderr)
            sys.exit(1)
        
        # 2. Détection de lignes malformées/unéquilibrées
        if p.row_count > 1 and not p.is_transposed:
            try:
                with open(fp, encoding=p.encoding, errors="replace") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                col_counts = [len(l.split(p.delimiter)) for l in lines[:10]]
                if len(set(col_counts)) > 1:
                    print("Warning: Malformed or unbalanced rows detected", file=sys.stderr)
            except Exception:
                pass

        output = {
            "delimiter": p.delimiter,
            "encoding": p.encoding,
            "transposed": p.is_transposed,
            "brand": p.brand_detected,
            "columns": p.column_count,
            "rows": p.row_count,
        }
        print(json.dumps(output))
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
