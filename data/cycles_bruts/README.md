# Cycles bruts — source de référence (simulation réaliste)

Ce dossier contient un **export de cycles bruts simulé** au format d'un export
industriel type EUROMAP/Arburg, destiné à alimenter le modèle HDT
(`ml/process_drift.py`) et à servir de source de démonstration pour le pilote.

## Contenu

| Fichier | Machine | Cycles |
|---|---|---|
| `machine_cycles_bruts_152.csv` | Engel victory 160 | 2 500 |
| `machine_cycles_bruts_1003.csv` | Arburg Allrounder 520A | 2 500 |
| `machine_cycles_bruts_606.csv` | Presse deux plateaux 450 t | 2 500 |
| `machine_cycles_bruts_870.csv` | Machine neuve 280 t (inconnue du HDT) | 2 500 |

Total : **10 000 cycles** sur une fenêtre d'export d'environ 2,5 jours
(2026-07-27 06:00 → 2026-07-29 08:44), générés avec la graine `42`.

## Format (contrat exact du modèle HDT)

Colonnes, dans l'ordre :

```
timestamp, machine_erp_ref,
cycle_time_s, dosing_time_s, injection_time_s, cooling_time_s,
cushion_mm, switchover_position_mm, switchover_pressure_bar, peak_pressure_bar,
clamp_force_kn, mold_temperature_c,
barrel_temp_zone1_c, barrel_temp_zone2_c, barrel_temp_zone3_c, oil_temperature_c,
energy_kwh, scrap_flag
```

- `timestamp` : horodatage local naïf (`%Y-%m-%d %H:%M:%S.%f`), cadence de
  30–90 s entre deux cycles, cohérent avec l'export historique d'entraînement.
- `machine_erp_ref` : référence ERP de la machine.
- 15 features numériques brutes en unités SI (temps en s, pressions en bar,
  températures en °C, force en kN, énergie en kWh), arrondies à 3 décimales.
- `scrap_flag` : 0/1, cycle rebuté ou non.

## Provenance et honnêteté

- **Données 100 % synthétiques** : générées par
  `scripts/generate_cycles_bruts.py` (graine fixe → sortie byte-identique).
  Il s'agit d'une **simulation réaliste d'un export d'atelier**, pas d'un
  export terrain réel.
- Les profils machines (consignes, bruit capteur, volatilité normale) sont
  **calibrés sur les données d'entraînement HDT**
  (`data/scenarios/industrial_demo/machine_cycles_*.csv`) : régimes stables
  par machine, bruit capteur plausible, épisodes de dérive lente avec
  oscillations, rebuts isolés + rafales dans les épisodes (~1,8 % du total).
- La machine `870` n'a **pas** été vue à l'entraînement : elle exerce le
  repli sur le modèle global de l'artefact HDT.

## Limites connues (qualification honnête)

Mesuré sur la graine 42 avec l'artefact `process_drift_hdt_v1` (sklearn 1.9.0) :

| Indicateur | Valeur |
|---|---:|
| Taux d'alerte HDT global sur ce jeu | **18,5 %** |
| Taux d'alerte attendu sur le domaine d'entraînement | ~2,4 % |
| Taux d'alerte — top 10 % volatilité (épisodes) | **38,5 %** |
| Taux d'alerte — bottom 50 % volatilité (stable) | 15,2 % |
| Plage de scores d'anomalie | 0,36 – 0,70 |

Lecture : le modèle HDT **réagit bien aux épisodes de dérive** (sur-détection
nette : 38,5 % vs 15,2 %), mais ce jeu sort **partiellement du domaine
d'entraînement** : le bruit de fond stable déclenche ~15 % d'alertes au lieu
de ~2 %. Le modèle n'est donc **pas validé pour ce jeu tel quel** ; il doit
être requalifié (ou ré-entraîné) sur un vrai export terrain. Ce jeu reste
utile comme **scénario de test hors distribution** pour le monitoring de
dérive (`ml/monitoring.py`).

## Régénérer

```bash
env -u PYTHONPATH .venv/bin/python scripts/generate_cycles_bruts.py --seed 42 --score
```

`--score` exécute le pipeline complet (prepare_inference_frame + predict) et
affiche le résumé ci-dessus. Autres options : `--cycles-per-machine`,
`--output-dir`, `--artifact`.
