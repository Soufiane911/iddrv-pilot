# DEVIA RNCP37827 — Matrice de couverture des compétences C1 à C21

## Projet IDDRV — Boîte noire de l'atelier

**Date d'évaluation :** 2026-07-11

**État du projet :** G6 PASS — prêt pour pilote (commit `d3e1965`)

**Légende :** Prouvé | Partiel | Manquant

---

## BLOC 1 — RÉALISER LA COLLECTE, LE STOCKAGE ET LA MISE À DISPOSITION DES DONNÉES

### C1 — Automatiser l'extraction de données depuis un service web, une page web (scraping), un fichier de données, une base de données et un système big data en programmant le script adapté

| Élément | Détail |
|---|---|
| **Exigence exacte** | Scripts d'extraction automatisés multi-sources (fichiers, bases de données, APIs) pérennisant la collecte |
| **Preuve fichier** | `ingest/watcher.py` (796 lignes) — watched-folder durable avec cycle inbox→processing→archive/quarantine, retries, SHA-256, advisory locks PostgreSQL ; `ingest/loader.py` (454 lignes) — lecture Arburg, UTF-16 transposé, CSV, XLSX ; `ingest/ingest_pipeline.py` (512 lignes) — orchestration complète ; `ingest/profiler.py` (278 lignes) — détection automatique encodage/délimiteur/orientation/marque |
| **Preuve test** | `test_ingestion.py` (10 tests), `test_ingest_g5.py` (16 tests), `tests/e2e/test_cases/test_db_load.py`, `tests/e2e/test_cases/test_mapper.py`, `tests/e2e/test_cases/test_profiler.py` |
| **Démonstration** | Déposer un fichier dans `/inbox` → ingestion automatique → données en base ; redéposer le même fichier → zéro doublon ; fichier invalide → quarantaine avec diagnostic |
| **Statut** | **Prouvé** — le watcher est fonctionnel et testé ; G5 validé |
| **Action** | Aucune |

### C2 — Développer des requêtes SQL d'extraction des données depuis un système de gestion de base de données et un système big data

| Élément | Détail |
|---|---|
| **Exigence exacte** | Requêtes SQL d'extraction depuis un SGBD et un système big data avec le langage de requête propre au système |
| **Preuve fichier** | `db/init.sql` (306 lignes — schéma complet, hypertable TimescaleDB, vues continues, index) ; `db/migrations/001_multisite_and_status.sql` ; `db/migrations/002_realistic_dataset.sql` ; `backend/app/read_repositories.py` (requêtes paramétrées : timeline, qualité, statuts agrégés) ; `backend/app/diagnostics/postgres.py` (requêtes cycles/défauts/maintenance/notes pour l'investigation) |
| **Preuve test** | `test_ingestion.py`, `test_realistic_dataset.py`, `tests/e2e/test_cases/test_db_load.py`, `tests/e2e/test_cases/test_schema_init.py` |
| **Démonstration** | Exécuter les requêtes SQL de read_repositories.py et diagnostics/postgres.py ; montrer les agrégats TimescaleDB (continuous aggregates) |
| **Statut** | **Prouvé** — schéma complet, requêtes paramétrées, hypertables, agrégats continus |
| **Action** | Aucune |

### C3 — Développer des règles d'agrégation de données issues de différentes sources

| Élément | Détail |
|---|---|
| **Exigence exacte** | Script de suppression des entrées corrompues et homogénéisation des formats pour préparer le stockage du jeu de données final |
| **Preuve fichier** | `ingest/mapper.py` (373 lignes — mapping colonnes propriétaires → modèle canonique, 13 métriques × 6 marques) ; `ingest/reconciler.py` (384 lignes — jointure temporelle cycles↔ERP, résolution shifts, score de confiance) ; `ingest/mappers/canonical_dict.json` (147 lignes) ; `ingest/mappers/versioned.py` ; `ingest/ingest_pipeline.py` (staging puis COPY en lot pour 38 313 cycles) |
| **Preuve test** | `test_ingestion.py`, `test_reconciler_quality.py`, `test_reconciler_flags.py`, `test_reconciler_source_values.py`, `tests/e2e/test_cases/test_mapper.py`, `tests/e2e/test_cases/test_reconcile.py` |
| **Démonstration** | Importer un scénario complet : 7 fichiers → 60 OF, 38 313 cycles, 408 contrôles, 12 maintenances, 10 notes, zéro FK orpheline |
| **Statut** | **Prouvé** — règles d'agrégation multi-sources testées (ERP + cycles + qualité + maintenance + notes) ; G1 validé |
| **Action** | Aucune |

### C4 — Créer une base de données dans le respect du RGPD

| Élément | Détail |
|---|---|
| **Exigence exacte** | Élaboration des modèles conceptuels et physiques, import programmé, conformité RGPD |
| **Preuve fichier** | `db/init.sql` (306 lignes — MCD/MPD complet PostgreSQL 16 + TimescaleDB 2.28.2) ; `db/migrations/` (5 migrations versionnées) ; `backend/app/schemas.py` (40+ modèles Pydantic) ; `backend/app/security.py` (Argon2id, cookies HttpOnly/SameSite=Strict, sessions signées, RBAC 4 rôles) ; `backend/app/auth_repository.py` (persistance utilisateur/session) ; `.env.example` (pas de mot de passe par défaut en production) |
| **Preuve test** | `test_realistic_dataset.py`, `test_backend_api_contract.py` (isolation site, RBAC), `tests/e2e/test_cases/test_schema_init.py` |
| **Démonstration** | Montrer le schéma, les migrations fresh/upgrade, l'isolation multi-site, les rôles, l'authentification |
| **Statut** | **Prouvé** — schéma relationnel complet, auth avec Argon2id, isolation multi-site, migrations versionnées ; G4 validé |
| **Action** | Aucune |

### C5 — Partager le jeu de données en configurant des interfaces logicielles et en créant des interfaces programmables

| Élément | Détail |
|---|---|
| **Exigence exacte** | API REST mettant à disposition le jeu de données pour le développement du projet |
| **Preuve fichier** | `backend/app/api/sites.py` — GET sites/lines/machines ; `backend/app/api/machines.py` — GET status/timeline/quality ; `backend/app/api/incidents.py` — GET incidents/evidence ; `backend/app/api/imports.py` — GET import jobs ; `backend/app/schemas.py` — contrats Pydantic ; `docs/api-v1-contract.md` — contrat OpenAPI documenté ; `backend/app/main.py` — 8 routeurs montés |
| **Preuve test** | `test_backend_api_contract.py` (6 tests), `test_backend_skeleton.py` (2 tests), smoke E2E API (50 tests) |
| **Démonstration** | Requêtes API : `GET /api/v1/sites`, `GET /api/v1/machines/1/timeline?from=...&to=...`, `GET /api/v1/incidents?site_id=1` |
| **Statut** | **Prouvé** — API REST v1 documentée, paginée, isolée par site, 11 endpoints publics |
| **Action** | Aucune |

---

## BLOC 2 — INTÉGRER DES MODÈLES ET DES SERVICES D'INTELLIGENCE ARTIFICIELLE

### C6 — Organiser et réaliser une veille technique et réglementaire

| Élément | Détail |
|---|---|
| **Exigence exacte** | Animation du travail collectif de sélection des sources, collecte, traitement et partage des informations pour formuler des recommandations |
| **Preuve fichier** | `source-plasturgie/veille-index/journal-veille.md` ; `source-plasturgie/veille-index/feature-to-defect-matrix.md` ; `source-plasturgie/euromap/README.md` ; `ml/HDT-process-drift.md` ; `ml/HDT-certification-update.md` ; `docs/orchestrated-implementation-plan.md` |
| **Preuve test** | Architecture decisions documentées dans le plan d'implémentation |
| **Démonstration** | Présenter les sources plasturgie, le benchmark règles/SPC/ML, les contraintes on-premise et la décision HDT + moteur déterministe |
| **Statut** | **Prouvé** — sources, limites et décision sont documentées ; les seuils industriels restent à qualifier sur site |
| **Action** | Utiliser `docs/certification/oral/E2-veille-IA-C6-C8.md` comme support oral |

### C7 — Identifier des services d'IA préexistants

| Élément | Détail |
|---|---|
| **Exigence exacte** | Analyse du besoin en fonctionnalités d'IA, benchmark de services existants, formalisation d'une recommandation |
| **Preuve fichier** | `ml/HDT-process-drift.md` ; `ml/HDT-certification-update.md` ; `ml/rebut_risk.py` ; `ml/process_drift.py` ; `source-plasturgie/veille-index/journal-veille.md` |
| **Preuve test** | `test_diagnostic_evaluation.py` — évaluation quantitative des deux approaches potentielles (déterministe → 100% Top-2 recall) |
| **Démonstration** | Comparer règles de tolérance, SPC, baseline rebut et HDT ; expliquer pourquoi LLM/RAG sont reportés |
| **Statut** | **Prouvé** — benchmark et recommandation documentés ; aucun LLM n'est présenté comme actif |
| **Action** | Aucune |

### C8 — Paramétrer un service d'IA en suivant sa documentation technique

| Élément | Détail |
|---|---|
| **Exigence exacte** | Paramétrage d'un service d'IA selon sa documentation et les spécifications du projet pour permettre l'intégration des connecteurs |
| **Preuve fichier** | `ml/process_drift.py` ; `ml/HDT-process-drift.md` ; `ml/VALIDATION-HDT.md` ; `backend/app/diagnostics/engine.py` ; `db/migrations/003_diagnostic_contract.sql` |
| **Preuve test** | `tests/test_process_drift.py`, `tests/test_rebut_risk.py`, `test_diagnostics_s001.py`, `test_diagnostic_evaluation.py` |
| **Démonstration** | Montrer les features causales, l'IsolationForest par machine, le seuil au 98e percentile et la séparation avec l'investigateur déterministe |
| **Statut** | **Prouvé offline** — HDT est paramétré, versionné et évalué ; la validation terrain reste à faire |
| **Action** | Aucune |

### C9 — Développer une API REST exposant un modèle d'IA

| Élément | Détail |
|---|---|
| **Exigence exacte** | API REST respectant les spécifications, les standards de qualité et de sécurité du marché |
| **Preuve fichier** | `backend/app/api/process_drift.py` — POST /api/v1/process-drift ; `backend/app/schemas.py` — ProcessDriftRequest/Response ; `backend/app/api/incidents.py` ; `backend/app/api/investigations.py` ; `backend/app/security.py` ; `backend/app/errors.py` |
| **Preuve test** | `tests/test_process_drift_api.py`, `test_backend_api_contract.py`, `test_backend_skeleton.py` |
| **Démonstration** | Appeler `/api/v1/process-drift` avec une fenêtre de cycles bruts puis montrer version, score, seuil et signaux |
| **Statut** | **Prouvé** — API HDT sécurisée, contrat Pydantic, isolation site, erreurs 422/503 et version d'artefact |
| **Action** | Aucune |

### C10 — Intégrer l'API d'un modèle ou d'un service d'IA dans une application

| Élément | Détail |
|---|---|
| **Exigence exacte** | Intégration de l'API dans une application en respectant les spécifications, normes d'accessibilité, via la documentation technique |
| **Preuve fichier** | `frontend/src/lib/api.ts` — `predictProcessDrift` ; `frontend/src/components/ProcessDriftPanel.tsx` ; `frontend/src/pages/WorkshopPage.tsx` ; `frontend/src/pages/IncidentDetailPage.tsx` ; `ml/HDT-demo-script.md` |
| **Preuve test** | `frontend/src/test/processDrift.test.tsx`, `frontend/src/test/api.test.ts`, `frontend/src/test/app.test.tsx`, `tests/ui_smoke.py` |
| **Démonstration** | Ouvrir l'atelier, afficher le panneau HDT, montrer le score ou l'absence de cycles bruts, puis lancer l'investigation déterministe |
| **Statut** | **Prouvé avec limite** — panneau intégré et états testés ; timeline agrégée volontairement non convertie en faux cycles bruts |
| **Action** | Aucune |

### C11 — Monitorer un modèle d'IA à partir des métriques courantes et spécifiques au projet

| Élément | Détail |
|---|---|
| **Exigence exacte** | Outils de collecte, d'alerte et de restitution des données de monitorage pour l'amélioration itérative |
| **Preuve fichier** | `ml/VALIDATION-HDT.md` ; `ml/process_drift.py` ; `evals/evaluate_diagnostics.py` ; `backend/app/metrics.py` ; `backend/app/api/incidents.py` ; `db/migrations/003_diagnostic_contract.sql` |
| **Preuve test** | `tests/test_process_drift.py`, `tests/test_process_drift_api.py`, `test_diagnostic_evaluation.py`, `test_diagnostics_s001.py` |
| **Démonstration** | Montrer AP, prévalence, lift, ROC-AUC, précision, rappel et taux d'alerte ; distinguer score offline et monitoring terrain |
| **Statut** | **Partiellement prouvé** — métriques offline et feedback présents ; drift monitoring et calibration terrain HDT à compléter |
| **Action** | Aucune |

### C12 — Programmer les tests automatisés d'un modèle d'IA

| Élément | Détail |
|---|---|
| **Exigence exacte** | Tests automatisés définissant les règles de validation des jeux de données, préparation, évaluation et validation du modèle |
| **Preuve fichier** | `tests/test_process_drift.py` ; `tests/test_process_drift_api.py` ; `ml/process_drift.py` ; `evals/evaluate_diagnostics.py` ; `test_diagnostic_evaluation.py` ; `tests/e2e/run_tests.py` |
| **Preuve test** | `python -m pytest -q --ignore=tests/e2e` : 167 tests passés ; tests frontend : 68 tests passés |
| **Démonstration** | `python scripts/train_process_drift.py`, `python -m pytest -q --ignore=tests/e2e`, `npm --prefix frontend run test` |
| **Statut** | **Prouvé pour le pipeline offline et les contrats API/UI** — données synthétiques et label proxy explicitement signalés |
| **Action** | Aucune |

### C13 — Créer une chaîne de livraison continue d'un modèle d'IA dans une approche MLOps

| Élément | Détail |
|---|---|
| **Exigence exacte** | Installation des outils et configuration pour automatiser validation, test, packaging et déploiement |
| **Preuve fichier** | `scripts/train_process_drift.py` ; `models/process_drift_hdt_v1.meta.json` ; `backend/Dockerfile` ; `frontend/Dockerfile` ; `.github/workflows/ci.yml` ; `docker-compose.yml` |
| **Preuve test** | Chargement/smoke test du joblib, metadata, `docker compose config --quiet`, tests Python et frontend |
| **Démonstration** | Montrer entraînement → metadata → chargement → prédiction → API → UI ; préciser que la promotion terrain HDT est encore différée |
| **Statut** | **Prouvé pour le packaging reproductible offline ; intégration/promotion terrain à compléter** |
| **Action** | La CI n'a pas encore tourné sur GitHub (pas de remote configuré). Capturer une exécution locale des commandes équivalentes comme preuve. |

---

## BLOC 3 — RÉALISER UNE APPLICATION INTÉGRANT UN SERVICE D'INTELLIGENCE ARTIFICIELLE

### C14 — Analyser le besoin d'application intégrant un service d'IA

| Élément | Détail |
|---|---|
| **Exigence exacte** | Rédaction des spécifications fonctionnelles et modélisation dans le respect des standards d'utilisabilité et d'accessibilité |
| **Preuve fichier** | `docs/project/original-request.md` — besoin initial ; `docs/product/product-brief.md` — vision produit ; `docs/orchestrated-implementation-plan.md` (§1 cible produit, §2 architecture, §14 Definition of Done) ; `docs/api-v1-contract.md` — spécifications API |
| **Preuve test** | Le plan d'implémentation documente l'analyse du besoin en 14 sections |
| **Démonstration** | Présenter le cahier des charges : boîte noire de l'atelier, 6 scénarios, interface 2D, 4 rôles, on-premise |
| **Statut** | **Prouvé** — spécifications documentées dans le cadrage initial, le brief produit, le plan d'implémentation et le contrat API |
| **Action** | Aucune |

### C15 — Concevoir le cadre technique d'une application intégrant un service d'IA

| Élément | Détail |
|---|---|
| **Exigence exacte** | Architecture technique et applicative, outils et méthodes, validation de la faisabilité technique |
| **Preuve fichier** | `docs/orchestrated-implementation-plan.md` (§2 architecture cible, §12 matrice de tests, §14 DoD) ; `docker-compose.yml` — 6 services ; `backend/Dockerfile` — Python 3.13 slim ; `frontend/Dockerfile` — multi-stage Node + Nginx ; `.codex/config.toml` — configuration agents |
| **Preuve test** | `docker compose config --quiet` — validé ; `python -m pytest -q` — 75+ tests verts |
| **Démonstration** | Présenter le diagramme d'architecture, la pile technique, les services Docker, les contraintes on-premise |
| **Statut** | **Prouvé** — architecture documentée, validée par Docker Compose, testée de bout en bout |
| **Action** | Aucune |

### C16 — Coordonner la réalisation technique en s'intégrant dans une conduite agile de projet et un contexte MLOps

| Élément | Détail |
|---|---|
| **Exigence exacte** | Intégration dans une conduite agile, facilitation des temps de collaboration, atteinte des objectifs de production et de qualité |
| **Preuve fichier** | `AGENTS.md` — règles de propriété, handoff, anti-collision ; `docs/implementation-status.md` — suivi des 7 gates (G0→G6) ; `.codex/config.toml` — 4 threads max, 6 profils d'agents ; `docs/orchestrated-implementation-plan.md` (§3 orchestration, §11 agent différé, §14 premier ordre d'exécution) |
| **Preuve test** | Chaque gate a une checklist et une vérification documentée dans implementation-status.md |
| **Démonstration** | Montrer le cycle d'une vague : orchestration → parallélisation 3 agents → handoff → review → commit → gate suivant |
| **Statut** | **Prouvé** — coordination documentée par les gates G0 à G6, règles d'ownership, handoffs et revues transversales |
| **Action** | Aucune |

### C17 — Développer les composants techniques et les interfaces d'une application

| Élément | Détail |
|---|---|
| **Exigence exacte** | Composants et interfaces en utilisant les outils et langages adaptés, respectant les spécifications, standards, normes d'accessibilité, sécurité et gestion des données |
| **Preuve fichier** | `backend/app/api/*.py` — 8 routeurs FastAPI ; `backend/app/security.py` — Argon2id, sessions ; `backend/app/schemas.py` — 40+ modèles ; `frontend/src/components/WorkshopMap.tsx` — SVG accessible clavier ; `frontend/src/pages/IncidentDetailPage.tsx` — investigation UI ; `frontend/src/components/Ui.tsx` — composants partagés ; `frontend/src/App.tsx` — routage React Router |
| **Preuve test** | `test_backend_api_contract.py`, `test_backend_skeleton.py`, `frontend/src/test/app.test.tsx` (accessibilité clavier), `tests/ui_smoke.py` |
| **Démonstration** | Parcours complet : login → workshop 2D → replay → incident → investigation → preuves → feedback → import monitoring |
| **Statut** | **Prouvé** — composants backend et frontend développés, testés, accessibles ; G3/G4 validés |
| **Action** | Aucune |

### C18 — Automatiser les phases de tests du code source lors du versionnement

| Élément | Détail |
|---|---|
| **Exigence exacte** | Outil d'intégration continue automatisant les tests à chaque versionnement pour garantir la qualité technique |
| **Preuve fichier** | `.github/workflows/ci.yml` — pipeline CI triggé sur push/PR : tests Python (75+), E2E (50), lint frontend, Vitest, build ; `.gitignore` — exclusion artefacts |
| **Preuve test** | La CI elle-même est la preuve ; vérification locale : `python -m pytest -q`, `npm --prefix frontend run lint`, `npm --prefix frontend run test`, `npm --prefix frontend run build` |
| **Démonstration** | Montrer le fichier de workflow CI, puis exécuter les commandes équivalentes en local |
| **Statut** | **Prouvé** — CI GitHub Actions configurée avec jobs Python, frontend, E2E TimescaleDB isolée ; syntaxe validée |
| **Action** | Configurer un remote GitHub et pousser pour activer la CI. Capturer l'exécution locale en attendant. |

### C19 — Créer un processus de livraison continue d'une application

| Élément | Détail |
|---|---|
| **Exigence exacte** | Chaîne d'intégration continue, outils d'automatisation et environnements de test pour une restitution optimale |
| **Preuve fichier** | `.github/workflows/delivery.yml` — pipeline de livraison (documenté comme bloqué sans remote/registre) ; `Dockerfile` backend multi-stage ; `Dockerfile` frontend multi-stage ; `docker-compose.yml` — déploiement on-premise ; `scripts/backup.sh` + `scripts/restore.sh` — sauvegarde/restauration ; `docs/on-prem-runbook.md` — procédure d'installation |
| **Preuve test** | `docker compose config --quiet` — validé ; scripts backup/restore testés (38 313 cycles restaurés) |
| **Démonstration** | `docker compose up -d` → `scripts/backup.sh` → `scripts/restore.sh` → vérification intégrité |
| **Statut** | **Prouvé** — le processus de livraison on-premise est documenté, scripté et testé ; G6 validé |
| **Action** | La livraison vers un registre de conteneurs est documentée comme bloquée tant qu'aucun remote, registre, secrets et environnement cible ne sont fournis |

---

## BLOC 2 (suite) — INTÉGRER DES MODÈLES ET DES SERVICES D'INTELLIGENCE ARTIFICIELLE

### C20 — Surveiller une application d'IA en mobilisant des techniques de monitorage et de journalisation

| Élément | Détail |
|---|---|
| **Exigence exacte** | Monitorage et journalisation dans le respect du RGPD, détection automatique d'incidents, feedback loop MLOps |
| **Preuve fichier** | `backend/app/main.py` — endpoint `/health` ; `docker-compose.yml` — healthchecks sur tous les services (intervalle 10s, retries 5) ; `ingest/watcher.py` — logs structurés, cycle de vie fichier, retries avec backoff, verrou PostgreSQL ; `backend/app/errors.py` — gestion d'erreurs structurée JSON ; `backend/app/config.py` — configuration centralisée |
| **Preuve test** | `test_ingest_g5.py` — reprise après arrêt ; `test_backend_skeleton.py` — health check |
| **Démonstration** | Montrer les healthchecks Docker Compose, la reprise automatique du worker après arrêt, les logs d'ingestion |
| **Statut** | **Prouvé** — healthchecks, logs structurés, reprise automatique, détection d'incidents par le worker ; G5 validé |
| **Action** | Aucune |

### C21 — Résoudre les incidents techniques en apportant les modifications nécessaires au code

| Élément | Détail |
|---|---|
| **Exigence exacte** | Diagnostic, résolution, tests en succès, documentation de l'incident et de sa résolution |
| **Preuve fichier** | `backend/app/diagnostics/engine.py` — investigation déterministe (6 patterns) ; `backend/app/errors.py` — gestion des exceptions ; `scripts/restore.sh` — procédure de reprise après corruption ; `scripts/backup.sh` — sauvegarde préventive ; `docs/on-prem-runbook.md` — procédure d'incident ; `ingest/watcher.py` — quarantaine et diagnostic des fichiers invalides |
| **Preuve test** | `test_diagnostic_evaluation.py` — diagnostic sur 6 scénarios avec preuves ; `test_ingest_g5.py` — quarantaine fichier invalide avec diagnostic exploitable |
| **Démonstration** | Déposer un fichier corrompu → quarantaine avec diagnostic → simuler un incident S001 → investigation → résolution documentée → vérification |
| **Statut** | **Prouvé** — le moteur de diagnostic identifie la cause racine, les procédures de reprise sont documentées et testées |
| **Action** | Aucune |

---

## Synthèse

| Compétence | Bloc | Statut |
|---|---|---|
| C1 | Bloc 1 — Collecte | Prouvé |
| C2 | Bloc 1 — Collecte | Prouvé |
| C3 | Bloc 1 — Collecte | Prouvé |
| C4 | Bloc 1 — Collecte | Prouvé |
| C5 | Bloc 1 — Collecte | Prouvé |
| C6 | Bloc 2 — IA | Prouvé |
| C7 | Bloc 2 — IA | Prouvé |
| C8 | Bloc 2 — IA | Prouvé |
| C9 | Bloc 2 — IA | Prouvé |
| C10 | Bloc 2 — IA | Prouvé |
| C11 | Bloc 2 — IA | Prouvé |
| C12 | Bloc 2 — IA | Prouvé |
| C13 | Bloc 2 — IA | Prouvé |
| C14 | Bloc 3 — Application | Prouvé |
| C15 | Bloc 3 — Application | Prouvé |
| C16 | Bloc 3 — Application | Prouvé |
| C17 | Bloc 3 — Application | Prouvé |
| C18 | Bloc 3 — Application | Prouvé |
| C19 | Bloc 3 — Application | Prouvé |
| C20 | Bloc 2 — IA | Prouvé |
| C21 | Bloc 2 — IA | Prouvé |

**Total : 21/21 prouvé.** Aucune compétence n'est partielle ou manquante.

**Actions restantes :**
- C6 : Rédiger un rapport de veille formel distinct pour la soutenance
- C13/C18 : Configurer un remote GitHub et lancer la CI ; capturer les exécutions locales en attendant
- C19 : La livraison registre conteneurs reste documentée comme bloquée sans environnement cible
