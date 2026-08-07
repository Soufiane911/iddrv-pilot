# Rapport écrit DEVIA — organisation

Soutenance septembre 2026 · DEVIA RNCP37827 · 3 blocs · 5 épreuves (E1–E5).

Ce dossier contient le **rapport écrit officiel**, un fichier par épreuve.
Les plans d'oral restent dans `docs/certification/oral/` ; les rapports ici sont
la version longue (15–20 p. pour E2/E3/E4, 2–5 p. pour E1/E5).

## Ordre de rédaction (ne pas changer)

**E2 → E5 → E1 → E3 → E4**

1. **E2** d'abord : la plus fragile (le « service IA » est déterministe, pas un LLM — le jury doit le lire clairement). Le plan oral E2 est déjà quasi complet : la matière est prête.
2. **E5** ensuite : court (2–5 p.), mais exige une **fiche incident réelle** à produire (C21).
3. **E1** : court, exige la **note RGPD** (C4).
4. **E3** : s'appuie sur E2 (mêmes métriques HDT), le travail de fond est fait.
5. **E4** : le plus long, en dernier (récit des gates C16 + preuve CI C18 + captures parcours C17).

## Suivi

| # | Fichier | Pages cible | Statut | Bloqué par |
|---|---|---|---|---|
| 1 | [E2 — Veille et choix IA](./E2-veille-IA-C6-C8.md) | 15–20 | 📝 **brouillon rédigé** | relecture + figures + mise en page |
| 2 | [E5 — Monitorage et incident](./E5-monitorage-incident-C20-C21.md) | 2–5 | 📝 **brouillon rédigé** (incident reproduit ✅) | captures visuelles optionnelles |
| 3 | [E1 — Données](./E1-donnees-C1-C5.md) | 2–5 | 📝 **brouillon rédigé** (volumes vérifiés ✅, note RGPD ✅) | captures visuelles optionnelles |
| 4 | [E3 — Service IA](./E3-service-IA-C9-C13.md) | 15–20 | 📝 **brouillon rédigé** | captures API/UI + preuve CI (C13) |
| 5 | [E4 — Application](./E4-application-C14-C19.md) | 15–20 | 📝 **brouillon rédigé** | captures parcours UI (C17) + preuve CI (C18) |

## Preuves transversales à produire en parallèle

- [x] Preuve CI locale : captures des commandes équivalentes exécutées (C13, C18) — **fait 2026-08-07** : pytest 46 ✅, Vitest 72 ✅, lint ✅, build ✅, compose ✅ (`preuves/transversal/preuve-ci-locale.md`)
- [ ] Captures démo parcours UI (C10, C17) — reste à faire
- [x] Fiche incident « fichier corrompu » datée (C21) — **fait 2026-08-07** (incident reproduit, `preuves/E5/fiche-incident.md`)
- [x] Note RGPD minimale (C4) — **fait 2026-08-07** (`preuves/E1/note-rgpd.md`)

## Dossier preuves

Chaque épreuve a son sous-dossier dans [`preuves/`](./preuves/) avec sa checklist
(captures, fiches, exports à déposer au fil de l'eau) :

| Dossier | Épreuve |
|---|---|
| [`preuves/E1/`](./preuves/E1/README.md) | Données — captures import/profilage, note RGPD, volumes |
| [`preuves/E2/`](./preuves/E2/README.md) | Veille IA — journal daté, benchmark, métriques HDT |
| [`preuves/E3/`](./preuves/E3/README.md) | Service IA — capture API, panneau UI, preuve CI |
| [`preuves/E4/`](./preuves/E4/README.md) | Application — captures parcours, schéma, preuve CI |
| [`preuves/E5/`](./preuves/E5/README.md) | Monitorage — fiche incident, quarantaine, logs |
| [`preuves/transversal/`](./preuves/transversal/README.md) | Commun — suite de tests, build, compose, vidéo |

## Règles d'écriture (issues du dossier oral)

- **Concret d'abord, jamais de remplissage** : chaque paragraphe doit porter une information (chiffre, décision, preuve). Un texte volumineux qui ne dit rien de concret dessert l'oral — le jury note ce qui est démontré, pas le poids du PDF. Si les pages cibles ne sont pas atteintes, on complète par des **annexes utiles** (contrats API, extraits de tests, captures, journal de veille), pas par du texte dilué.
- Dire **« prêt pour pilote »**, jamais « validé sur le terrain ».
- Ne pas annoncer de RAG, d'agent OpenAI ou de modèle entraîné comme opérationnel.
- Chaque affirmation = une preuve : fichier, test, commande ou capture.
- `ground_truth.json` est évaluation-only : ne jamais le citer comme donnée d'entraînement ou source runtime.
- Les métriques HDT viennent d'un **holdout synthétique** : le dire explicitement, sans ambiguïté.

## Sources principales par épreuve

| Épreuve | Sources |
|---|---|
| E1 | `docs/certification/oral/E1-donnees-C1-C5.md`, `docs/superpowers/specs/industrial-ingestion-backend-db-design.md`, `ingest/*.py`, `db/init.sql`, `docs/api-v1-contract.md`, `docs/code-wiki.md` |
| E2 | `docs/certification/oral/E2-veille-IA-C6-C8.md`, `source-plasturgie/`, `ml/HDT-certification-update.md`, `ml/VALIDATION-HDT.md`, `note/2026-08-03.md` |
| E3 | `docs/certification/oral/E3-service-IA-C9-C13.md`, `ml/process_drift.py`, `scripts/train_process_drift.py`, `models/process_drift_hdt_v1.*`, `tests/test_process_drift*.py` |
| E4 | `docs/certification/oral/E4-application-C14-C19.md`, `docs/orchestrated-implementation-plan.md`, `docs/product/product-brief.md`, `docs/on-prem-runbook.md`, `docs/product/frontend-evidence.md`, `docs/code-wiki.md` |
| E5 | `docs/certification/oral/E5-monitorage-incident-C20-C21.md`, `docs/on-prem-runbook.md`, `docker-compose.yml`, logs et statuts d'import |
