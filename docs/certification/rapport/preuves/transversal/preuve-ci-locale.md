# Preuve CI locale — exécution réelle du 2026-08-07

Commandes équivalentes à la chaîne CI, exécutées localement sur la branche
`codex/iddrv-pilot` (environnement : venv projet Python 3.13, Node frontend).

## Résultats

| Vérification | Commande | Résultat |
|---|---|---|
| Tests Python (ML + ingestion + API) | `python -m pytest -q tests/test_process_drift.py tests/test_process_drift_api.py tests/test_process_drift_monitoring.py tests/test_rebut_risk.py tests/test_rebut_risk_api.py tests/test_ingest_g5.py` | **46 passed in 6.11s** |
| Lint frontend | `npm --prefix frontend run lint` (eslint `--max-warnings 0`) | **OK** (0 warning) |
| Tests frontend | `npm --prefix frontend run test` (Vitest) | **72 passed** (6 fichiers, 3.09s) |
| Build production | `npm --prefix frontend run build` | **✓ built in 1.71s** |
| Compose | `docker compose config --quiet` | **OK** |

## Sortie brute (extraits)

```text
=== PYTEST ===
.............................................. [100%]
46 passed in 6.11s

=== FRONTEND LINT ===
> eslint . --max-warnings 0
(0 problème)

=== FRONTEND VITEST ===
Test Files  6 passed (6)
     Tests  72 passed (72)
Duration    3.09s

=== FRONTEND BUILD ===
dist/assets/index-DlS04NK5.js   387.05 kB │ gzip: 115.43 kB
✓ built in 1.71s

=== COMPOSE CONFIG ===
compose config: OK
```

## Usage dans les rapports

- **C13 (E3)** : preuve de la chaîne de livraison du modèle HDT (train + tests).
- **C18 (E4)** : preuve de la chaîne de tests/lint/build de l'application.
- **C19/C20 (E4/E5)** : `docker compose config` valide.

*Note : la suite E2E (`tests/e2e/run_tests.py`) et les volumes de démo (38 313
cycles) ont été validés lors du gate G6 ; les résultats de référence sont dans
`docs/implementation-status.md`.*
