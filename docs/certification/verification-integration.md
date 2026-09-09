# Vérification de consolidation — 9 septembre 2026

## Version et sauvegarde

Base consolidée : `01fcb4fa8daa8261ca34cf2e44171a4d7836af5b` (release locale, atelier/planning et smoke navigation). Les correctifs et ce bilan sont enregistrés ensemble dans le commit consultable avec `git log -1 -- docs/certification/verification-integration.md`. Tests exécutés sur l'arbre modifié avant commit, pas sur GitHub.

Ancien main : `ef621ff51ef47724ef5ca784116adb55136c83fd`, préservé par `refs/safety/consolidation-20260909-main`. Sauvegarde privée : `/Users/soufianehamzaoui/iddrv-local-backups/consolidation-20260909-145908`. Bundle autonome ciblé restauré et vérifié par fsck ; archives des fichiers sélectionnés vérifiées SHA256. Ce n'est pas une sauvegarde globale des 45 Go d'historique/expériences. Aucun nettoyage, suppression de branche ou push.

## Changements vérifiés

- E2E : préserver `schema_migrations` lors du nettoyage, respecter le `site_id` obligatoire dans les fixtures, corriger le patch de configuration DB, vérifier l'idempotence du registre. Rapports conservés par CI même en échec.
- CI Python : cibler explicitement `tests/`. La commande sans chemin collectait aussi les copies expérimentales non suivies de `output/` (21 erreurs de collecte locales) ; aucune archive ni assertion supprimée.
- Modèle : chaîne de package candidat et workflow manuel sans déploiement, manifeste du modèle servi, normalisation UTC avant recherche de doublons, contrat de fichiers/hashes obligatoire avant chargement. Aucun binaire modèle remplacé.
- Exploitation : collector/scorer et healthchecks du pilote, migrations isolées, verrou et suivi des tags, rollback vers la dernière version saine après tentative échouée. Tests du script avec Docker factice, pas déploiement réel.
- Données/documentation : démonstrateur CSV/JSON synthétiques vers SQLite temporaire, matrice sourcée, propositions RGPD et recette. Ni scraping/big data ni intégration PostgreSQL applicative revendiqués par ce démonstrateur.

## Résultats réels

| Commande | Résultat | Portée |
| --- | --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest -q tests --ignore=tests/e2e` | 476 passed, 37 skipped, 22,82 s | Suite locale Python, incluant certains tests expérimentaux non suivis ; pas un total garanti dans un clone publié |
| `npm --prefix frontend run test` | 171 passed, 2 skipped | Vitest/jsdom |
| `npm --prefix frontend run lint` | code 0 | ESLint |
| `npm --prefix frontend run build` | code 0 | TypeScript et Vite |
| `CI=true npm --prefix frontend run test:e2e -- --project=chromium` | 36 passed | Navigateur Chromium, mode démo, pas API/DB vivantes |
| `python3 tests/e2e/run_tests.py -t1,2` | 54 passed, 2 skipped, code 0 | TimescaleDB 2.28.2-pg16 et Redis 7 temporaires réels |
| `python3 -m pytest -q tests/e2e/test_safety_guards.py` | 7 passed | Même environnement E2E isolé |
| `bash -n deploy/deploy-pilot.sh` | code 0 | Syntaxe, pas livraison réelle |

Les suites ciblées ML/operations/données sont incluses dans la suite Python et ne doivent pas être additionnées pour gonfler un total. Les deux tests E2E ignorés nécessitent `ERP_TEST_DATABASE_URL` et `TELEMETRY_TEST_DATABASE_URL`, non fournis. Les autres skips ne sont pas des succès.

Python de validation : Anaconda 3.13.9, sklearn 1.7.2, dépendances existantes ; pas d'installation. Le modèle de la release consolidée a le SHA256 `29dea3dca96ad0e3bfa1b1e54a4f7e55bd0d351a61cbe209ab84962530424eb6`, distinct de celui de l'ancien main distant. L'écart sklearn précédemment observé ne se reproduit pas sur cet artefact consolidé.

E2E : deux conteneurs propres en tmpfs, ports loopback, sans volumes utilisateur, supprimés nommément. Preuves expurgées locales dans `/tmp/iddrv-integrated-verification/` (éphémères, non incluses dans Git). Logs parent : `/tmp/iddrv-integrated-backend-final.log`, `/tmp/iddrv-integrated-frontend-tests.log`, `/tmp/iddrv-integrated-frontend-build.log`, `/tmp/iddrv-integrated-playwright.log`.

## Ce qui reste à faire

1. Autoriser puis publier le commit final et rejouer CI/GitHub Actions. Aucun résultat CI distant récent n'est revendiqué. Les logs du run E2E historique étaient inaccessibles ; les défauts sont prouvés localement, pas attribués avec certitude à ce run.
2. Exécuter les intégrations ERP/télémétrie ignorées et la recette navigateur → authentification → API → DB → modèle ; valider clavier/zoom/accessibilité hors mode démo.
3. Exécuter livraison et restauration en environnement autorisé, tester migrations avec sauvegarde DB et compatibilité schéma. Le rollback testé avec Docker factice n'est pas une restauration réelle.
4. Brancher métriques du scorer vivant et canal d'alerte opérationnel. `monitor-local.py` reste un calcul synthétique avec canal fichier explicitement local, sans réception humaine.
5. Compléter sources C1/C2, modèle/registre/procédure RGPD C4, benchmark C7, traces authentiques C6/C16 et besoins/recette C14/C15. Pas de validation client ou historique de veille inventé.
6. Compléter provenance originale du modèle et validation temporelle : split existant sans purge explicite de l'horizon futur, métriques proxy synthétiques, pas performance industrielle démontrée. Workflow candidat ne déploie pas.
7. Sélectionner et versionner les preuves locales utiles après vérification des données sensibles ; `Preuve-manquante/`, expériences HDT, résultats et simulateur ne sont pas intégrés aveuglément. Le simulateur incomplet reste hors priorité.

Les compétences C1–C21 ne sont pas déclarées toutes acquises. Ce bilan distingue code corrigé, exécution locale, démonstration synthétique et actions distantes non effectuées.
