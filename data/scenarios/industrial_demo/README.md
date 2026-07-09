# Industrial Demo Dataset

Dataset industriel fictif pour tester un agent capable de correler donnees ERP, cycles machine, qualite, defauts et causes probables.

## Fichiers

| Fichier | Description |
|---------|-------------|
| `erp_orders.xlsx` | Ordres de fabrication (ERP) |
| `machine_cycles_152.csv` | Cycles machine - Presse 152 (petite) |
| `machine_cycles_1003.csv` | Cycles machine - Presse 1003 (moyenne) |
| `machine_cycles_606.csv` | Cycles machine - Presse 606 (grande) |
| `quality_checks.csv` | Controles qualite |
| `maintenance_events.csv` | Evenements maintenance |
| `operator_notes.csv` | Notes operateur |
| `ground_truth.json` | Verite terrain (6 scenarios de defauts) |

## Schema de correlation

- `production_order_id` -> relie ERP, cycles, qualite et notes
- `machine_erp_ref` -> relie ERP, cycles, maintenance et notes
- `timestamp` -> correlation temporelle entre toutes les sources
- `product_ref` -> relie ERP et qualite
- `tool_ref` -> relie ERP a l'outillage

## Scenarios de defauts

| ID | Machine | Defaut | Cause |
|----|---------|--------|-------|
| S001 | 152 | short_shot | Temperature zone 2 trop basse |
| S002 | 1003 | flash | Pression injection trop elevee |
| S003 | 606 | warpage | Refroidissement instable |
| S004 | 1003 | bubbles | Changement matiere sans purge |
| S005 | 152 | multiple | Redemarrage apres arret |
| S006 | 606 | dimension_out_of_tolerance | Usure progressive du moule |

## Statistiques

- Periode : 7 jours (10-16 fevrier 2025)
- 3 machines d'injection plastique (152, 1003, 606)
- 60 ordres de fabrication
- 38313 cycles machine
- 408 controles qualite
- 12 evenements maintenance
- 10 notes operateur
- 6 scenarios de defauts injectes
- Donnees imparfaites : valeurs manquantes, bruit, ambiguites
