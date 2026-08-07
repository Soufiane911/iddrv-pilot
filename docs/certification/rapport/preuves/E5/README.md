# Preuves E5 — Monitorage et incident (C20–C21)

Checklist de ce qu'on déposera ici pour finaliser `../E5-monitorage-incident-C20-C21.md`.
Le brouillon du rapport est rédigé (2026-08-07) avec un **incident réellement
reproduit** : fichier corrompu déposé dans l'inbox, quarantaine automatique vérifiée.

## Déposé

- [x] `fiche-incident.md` — fiche complète INC-2026-08-07-001 avec traces de la reproduction réelle (C21)
- [x] `logs-anonymises.txt` — traces de la reproduction (commandes, état base, probe) dans la fiche (C20/C21)

## Reste à déposer (captures visuelles, si souhaité)

- [ ] `capture-inbox.png` — capture du fichier dans l'inbox avant traitement (C21)
- [ ] `capture-quarantaine.png` — capture du fichier en quarantaine (C21)
- [ ] `capture-probe.png` — capture du résultat `probe` en lecture seule (C21)
- [ ] `capture-health.png` — capture `/health` et/ou `docker compose ps` (C20)
- [ ] `capture-metrics.png` — capture `/metrics` protégé (C20)

## Sources déjà dans le repo (à citer, pas à copier)

- `docs/certification/oral/E5-monitorage-incident-C20-C21.md` (fiche + questions probables)
- `docs/on-prem-runbook.md`, `docker-compose.yml`
- `ingest/` (watcher, profiler, loader, probe), `data/processing/.worker_heartbeat`
- `tests/test_ingest_g5.py`
