# Preuves E3 — Service IA (C9–C13)

Checklist de ce qu'on déposera ici pour finaliser `../E3-service-IA-C9-C13.md`.
Le brouillon du rapport est rédigé (2026-08-07), appuyé sur E2.

## Déposé

- [x] Contrat API, tests et métriques — **déjà dans le repo** (cités dans le rapport) : `backend/app/api/process_drift.py`, `schemas.py`, `tests/test_process_drift*.py`, `models/process_drift_hdt_v1.meta.json`

## Reste à déposer (preuves visuelles — C13/C9)

- [ ] `preuve-ci-locale/` — captures des commandes exécutées : `train_process_drift.py` + `pytest tests/test_process_drift*.py` + lint (C13)
- [ ] `capture-api-process-drift.png` — appel réel de `POST /api/v1/process-drift` + réponse JSON (C9)
- [ ] `capture-api-erreur.png` — rejet d'une fenêtre agrégée sans variables process (422) (C9)
- [ ] `capture-panneau-ui.png` — `ProcessDriftPanel` : état dérive détectée avec score/seuil/signaux (C10)

## Sources déjà dans le repo (à citer, pas à copier)

- `backend/app/api/process_drift.py`, `backend/app/schemas.py`
- `frontend/src/components/ProcessDriftPanel.tsx`, `frontend/src/pages/WorkshopPage.tsx`
- `ml/process_drift.py`, `scripts/train_process_drift.py`, `models/process_drift_hdt_v1.*`
- `tests/test_process_drift.py`, `tests/test_process_drift_api.py`, `frontend/src/test/processDrift.test.tsx`
