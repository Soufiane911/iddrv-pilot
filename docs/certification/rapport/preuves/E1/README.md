# Preuves E1 — Données (C1–C5)

Checklist de ce qu'on déposera ici pour finaliser `../E1-donnees-C1-C5.md`.
Le brouillon du rapport est rédigé (2026-08-07) ; volumes vérifiés sur les
sources (`data/raw/` : 38 313 cycles, 60 OF).

## Déposé

- [x] `note-rgpd.md` — note RGPD (C4) rédigée
- [x] `volumes-verifies.md` — volumes vérifiés sur les sources (38 313 cycles / 60 OF), intégrés au rapport E1 §5

## Reste à déposer (captures visuelles, si souhaité)

- [ ] `capture-profilage.png` — profiler qui détecte encodage/délimiteur/orientation d'un fichier source (C1)
- [ ] `capture-import.png` — import réussi d'un fichier via API ou interface (C1, C5)
- [ ] `capture-import-idempotent.png` — deuxième dépôt du même fichier : aucun doublon (C1)
- [ ] Rejouer la base de démo avant l'oral (les 38 313 cycles ne sont pas chargés en base actuellement)

## Sources déjà dans le repo (à citer, pas à copier)

- `ingest/profiler.py`, `ingest/mapper.py`, `ingest/reconciler.py`, `ingest/watcher.py`, `ingest/loader.py`
- `db/init.sql`, `docs/api-v1-contract.md`
- `docs/superpowers/specs/industrial-ingestion-backend-db-design.md`
