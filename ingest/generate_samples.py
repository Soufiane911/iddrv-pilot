"""
IDDRV — Générateur de données d'exemples réalistes
====================================================

Simule des exports de machines de plasturgie (Arburg, Engel) et un export ERP/TRS.
Ces fichiers permettent de tester le pipeline d'ingestion sans données réelles.

Fichiers générés :
1. data/samples/arburg_1003_cycles.txt     — Format protocole Arburg (tabulaire + métadonnées)
2. data/samples/engel_152_cycles.csv       — Format Engel CSV semi-colon
3. data/samples/transposed_606_tubes.txt   — Format transposé UTF-16 (type Tubes)
4. data/samples/erp_trs_fevrier.xlsx       — Export TRS ERP (format XLSX)
"""

import os
import csv
import random
import math
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path("data/samples")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Seed pour reproductibilité
random.seed(42)


def _gen_cycle_value(nominal: float, drift_pct: float = 0.05, sigma_pct: float = 0.02) -> float:
    """Génère une valeur avec bruit gaussien et dérive lente."""
    noise = random.gauss(0, nominal * sigma_pct)
    drift = nominal * drift_pct * random.uniform(-1, 1)
    return round(max(0, nominal + noise + drift), 3)


def generate_arburg_protocol(
    machine_id: str = "1003",
    machine_name: str = "1003 2 NOYAUX",
    moule: str = "M100321",
    matiere: str = "PA6-GF30",
    of: str = "O0824120601331",
    n_cycles: int = 200,
    nominal_cycle_s: float = 28.5,
    ref_datetime: datetime = None
) -> str:
    """
    Génère un fichier protocole Arburg réaliste.
    Format : en-têtes métadonnées puis colonnes t4015, t4012, ...
    """
    ref_datetime = ref_datetime or datetime(2025, 2, 11, 8, 0, 0)
    output_path = OUTPUT_DIR / f"arburg_{machine_id}_cycles.txt"

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        # Métadonnées en-tête (format Arburg réel)
        f.write(f"Machine;\t{machine_id} - {machine_name}\n")
        f.write(f"Moule;\t{moule}\n")
        f.write(f"Matière;\t{matiere}\n")
        f.write(f"Ordre Fab.;\t{of}\n")
        f.write(f"Date début;\t{ref_datetime.strftime('%d.%m.%Y %H:%M')}\n")
        f.write(f"Opérateur;\tOP001\n")
        f.write(f"Logiciel;\tSelogica V24.0\n")
        f.write("\n")

        # En-tête colonnes
        headers = ["t007", "t4015", "t4012", "t4018", "V4062", "V4065", "p4072", "p4071", "f4090", "f077", "f1403"]
        f.write(";".join(headers) + "\n")

        # Unités
        units = ["h:min", "s", "s", "s", "cm³", "cm³", "bar", "bar", "kN", "-", "-"]
        f.write(";".join(units) + "\n")

        # Cycles
        current_time = ref_datetime
        cycle_counter = 1
        for i in range(n_cycles):
            current_time += timedelta(seconds=nominal_cycle_s + random.gauss(0, 0.5))
            time_str = current_time.strftime("%H:%M")

            dosing = _gen_cycle_value(8.2, 0.08, 0.03)
            cycle_t = _gen_cycle_value(nominal_cycle_s, 0.04, 0.02)
            inj_t = _gen_cycle_value(1.85, 0.05, 0.02)
            cushion = _gen_cycle_value(4.2, 0.06, 0.02)
            sw_pos = _gen_cycle_value(52.3, 0.04, 0.01)
            sw_press = _gen_cycle_value(1050, 0.05, 0.02)
            peak_press = _gen_cycle_value(1180, 0.04, 0.02)
            clamp = _gen_cycle_value(980, 0.01, 0.005)
            good = 1 if random.random() > 0.02 else 0  # 2% de chutes

            row = [time_str, dosing, cycle_t, inj_t, cushion, sw_pos, sw_press, peak_press, clamp, good, cycle_counter]
            f.write(";".join(str(v) for v in row) + "\n")
            cycle_counter += 1

    print(f"[GEN] Arburg protocol: {output_path} ({n_cycles} cycles)")
    return str(output_path)


def generate_engel_csv(
    machine_id: str = "152",
    n_cycles: int = 150,
    nominal_cycle_s: float = 35.2,
    ref_datetime: datetime = None
) -> str:
    """
    Génère un fichier CSV Engel réaliste avec délimiteur virgule.
    """
    ref_datetime = ref_datetime or datetime(2025, 2, 11, 14, 0, 0)
    output_path = OUTPUT_DIR / f"engel_{machine_id}_cycles.csv"

    headers = ["Timestamp", "t_cycle", "t_dos", "t_inj", "v_mat", "v_sw", "p_sw", "p_max", "f_clamp", "n_good", "n_cycle"]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=",")
        writer.writerow(headers)

        current_time = ref_datetime
        for i in range(n_cycles):
            current_time += timedelta(seconds=nominal_cycle_s + random.gauss(0, 0.8))
            ts = current_time.strftime("%Y-%m-%d %H:%M:%S")

            dosing = _gen_cycle_value(9.1, 0.07, 0.03)
            cycle_t = _gen_cycle_value(nominal_cycle_s, 0.05, 0.02)
            inj_t = _gen_cycle_value(2.1, 0.05, 0.02)
            cushion = _gen_cycle_value(6.5, 0.07, 0.02)
            sw_pos = _gen_cycle_value(68.0, 0.04, 0.01)
            sw_press = _gen_cycle_value(850, 0.05, 0.02)
            peak_press = _gen_cycle_value(920, 0.04, 0.02)
            clamp = _gen_cycle_value(2700, 0.01, 0.005)
            good = 1 if random.random() > 0.015 else 0

            writer.writerow([ts, cycle_t, dosing, inj_t, cushion, sw_pos, sw_press, peak_press, clamp, good, i + 1])

    print(f"[GEN] Engel CSV: {output_path} ({n_cycles} cycles)")
    return str(output_path)


def generate_transposed_tubes(
    machine_id: str = "606",
    n_cycles: int = 100,
    nominal_cycle_s: float = 22.8,
    ref_date: date = None
) -> str:
    """
    Génère un fichier transposé (format Tubes) en UTF-16 LE.
    Lignes = paramètres, Colonnes = cycles (comme les vrais fichiers Tubes).
    """
    ref_date = ref_date or date(2025, 2, 11)
    output_path = OUTPUT_DIR / "transposed_606_tubes.txt"

    param_names = [
        "Date", "Heure", "Num Cycle",
        "CycleTime", "DosingTime", "InjectionTime",
        "CushionVolume", "SwitchoverPos", "SwitchoverPressure",
        "PeakPressure", "ClampForce", "OilTemp"
    ]

    # Construction des valeurs par colonne (cycle par cycle)
    cycle_data = []
    current_time = datetime.combine(ref_date, datetime.min.time()) + timedelta(hours=8)

    for i in range(n_cycles):
        current_time += timedelta(seconds=nominal_cycle_s + random.gauss(0, 0.5))
        # Fraction décimale de la journée
        seconds_since_midnight = (current_time - datetime.combine(ref_date, datetime.min.time())).total_seconds()
        time_fraction = seconds_since_midnight / 86400.0

        cycle_data.append([
            ref_date.strftime("%d.%m.%y"),
            f"{time_fraction:.9f}".replace(".", ","),
            str(i + 800),  # compteur cyclé depuis 800
            str(round(_gen_cycle_value(nominal_cycle_s, 0.05, 0.02), 3)).replace(".", ","),
            str(round(_gen_cycle_value(6.5, 0.07, 0.02), 3)).replace(".", ","),
            str(round(_gen_cycle_value(1.5, 0.05, 0.02), 3)).replace(".", ","),
            str(round(_gen_cycle_value(12.0, 0.06, 0.02), 3)).replace(".", ","),
            str(round(_gen_cycle_value(85.0, 0.04, 0.01), 3)).replace(".", ","),
            str(round(_gen_cycle_value(780, 0.05, 0.02), 1)).replace(".", ","),
            str(round(_gen_cycle_value(850, 0.04, 0.02), 1)).replace(".", ","),
            str(round(_gen_cycle_value(1980, 0.01, 0.005), 1)).replace(".", ","),
            str(round(_gen_cycle_value(42.0, 0.02, 0.005), 1)).replace(".", ","),
        ])

    # Transposer (lignes = paramètres)
    with open(output_path, "w", encoding="utf-16", newline="") as f:
        for param_idx, param_name in enumerate(param_names):
            values = [c[param_idx] for c in cycle_data]
            f.write(param_name + "\t" + "\t".join(values) + "\n")

    print(f"[GEN] Transposed Tubes (UTF-16): {output_path} ({n_cycles} cycles)")
    return str(output_path)


def generate_erp_trs_xlsx(
    machine_refs: list = None,
    month_start: date = None
) -> str:
    """
    Génère un fichier Excel TRS ERP avec plusieurs ordres de fabrication.
    Structure similaire aux vrais fichiers TRS_complet.xlsx.
    """
    machine_refs = machine_refs or ["1003", "606", "152"]
    month_start = month_start or date(2025, 2, 11)
    output_path = OUTPUT_DIR / "erp_trs_fevrier.xlsx"

    rows = []
    of_counter = 824120600
    sample_windows = {
        "1003": datetime(2025, 2, 11, 7, 30, 0),
        "606": datetime(2025, 2, 11, 7, 30, 0),
        "152": datetime(2025, 2, 11, 13, 30, 0),
    }

    for machine_ref in machine_refs:
        machine_names = {"1003": "1003 2 NOYAUX", "606": "606 PRESSE TUBES", "152": "PRESSE 152"}
        machine_name = machine_names.get(machine_ref, f"MACHINE {machine_ref}")

        # Générer 10 OFs par machine. Le premier OF couvre les exports machine
        # générés plus haut pour permettre une démo ERP ↔ cycles réellement liée.
        current_dt = sample_windows.get(
            machine_ref,
            datetime.combine(month_start, datetime.min.time()) + timedelta(hours=6)
        )
        for i in range(10):
            of_counter += 1
            duration_h = 4.0 if i == 0 else random.uniform(4, 12)
            nominal_cycle = random.uniform(15, 45)
            trs = random.uniform(0.60, 0.92)
            running_time = duration_h * trs
            good_parts = int((running_time * 3600) / nominal_cycle)
            scrap_count = int(good_parts * random.uniform(0.01, 0.04))

            rows.append({
                "Réf OF": f"O{of_counter}",
                "Réf. Machine": machine_ref,
                "Lib. Machine": machine_name,
                "Num Equipe": (i % 3) + 1,
                "Début Equipe": current_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "Fin Equipe": (current_dt + timedelta(hours=duration_h)).strftime("%Y-%m-%d %H:%M:%S"),
                "Réf. produit": f"PROD{random.randint(1000, 9999)}",
                "Lib. Produit": f"Pièce injection {random.randint(100, 999)}",
                "Réf. outil": f"M{random.randint(10000, 99999)}",
                "Réf. Matière": random.choice(["PA6-GF30", "PP-H", "ABS", "PETG", "POM"]),
                "Tps Disponible (h)": round(duration_h, 4),
                "Tps Fct Brut (h)": round(running_time, 4),
                "T.R.S.": round(trs, 4),
                "Cycle Moyen": round(nominal_cycle, 3),
                "Nb Cycles": good_parts + scrap_count,
                "Qté Pieces Bonnes": good_parts,
                "Total Rebuts": scrap_count,
            })

            current_dt += timedelta(hours=duration_h + random.uniform(0.5, 2))

    df = pd.DataFrame(rows)
    df.to_excel(output_path, index=False, sheet_name="Données_Audit")
    print(f"[GEN] ERP TRS XLSX: {output_path} ({len(rows)} ordres de fabrication)")
    return str(output_path)


if __name__ == "__main__":
    print("\n=== GÉNÉRATION DES DONNÉES D'EXEMPLES IDDRV ===\n")
    f1 = generate_arburg_protocol()
    f2 = generate_engel_csv()
    f3 = generate_transposed_tubes()
    f4 = generate_erp_trs_xlsx()

    print(f"\n✅ 4 fichiers générés dans {OUTPUT_DIR}/")
    print(f"  1. {f1}")
    print(f"  2. {f2}")
    print(f"  3. {f3}")
    print(f"  4. {f4}")
    print("\nPour tester le pipeline d'ingestion :")
    print(f"  python ingest/ingest_pipeline.py {f1} 1003")
    print(f"  python ingest/ingest_pipeline.py {f2} 152")
