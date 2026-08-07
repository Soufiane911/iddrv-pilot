# Preuves E4 — Application (C14–C19)

Checklist de ce qu'on déposera ici pour finaliser `../E4-application-C14-C19.md`.
Le brouillon du rapport est rédigé (2026-08-07) ; les chiffres de référence
(G1/G6) sont vérifiés dans `docs/implementation-status.md`.

## Déposé

- [x] Chiffres de référence — **dans le repo** (cités) : 60 OF / 38 313 cycles / 408 checks / 12 maintenances / 10 notes (G1) ; 50 E2E passés, 38 313 cycles restaurés (G6)
- [x] Récit des gates — **dans le repo** (cité) : `docs/orchestrated-implementation-plan.md` + `docs/implementation-status.md` (C16)

## Reste à déposer (captures visuelles — C17/C18)

- [ ] `schema-architecture.png` ou `.md` — schéma du monolithe modulaire (C15)
- [ ] `captures-parcours/` — parcours UI complet (C17) :
  - [ ] `01-connexion.png` — login
  - [ ] `02-sites.png` — liste des sites
  - [ ] `03-atelier.png` — atelier 2D avec machines
  - [ ] `04-replay.png` — replay temporel d'une machine
  - [ ] `05-incident.png` — liste des incidents
  - [ ] `06-investigation.png` — hypothèses + preuves
  - [ ] `07-feedback.png` — feedback humain enregistré
  - [ ] `08-imports.png` — page imports/santé
- [ ] `preuve-ci-locale/` — captures des commandes exécutées (C18) : `pytest`, `vitest`, `lint`, `build`
- [ ] `capture-3d.png` (optionnel) — atelier 3D si on la montre

## Sources déjà dans le repo (à citer, pas à copier)

- `docs/orchestrated-implementation-plan.md`, `docs/implementation-status.md` (récit des gates C16)
- `docs/on-prem-runbook.md`, `docker-compose.yml`, `scripts/backup.sh`, `scripts/restore.sh` (C19)
- `docs/product/frontend-evidence.md`, `docs/api-v1-contract.md`, `docs/code-wiki.md`
- `frontend/src/`, `backend/app/`, `tests/`
