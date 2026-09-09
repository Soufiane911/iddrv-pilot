# Inventaire des sources et observations

Base main observée : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a`. Les empreintes détaillées des seuls fichiers sélectionnés figurent dans `sources.json`. Aucun binaire modèle, log brut, PDF nominatif, export de données ni environnement n’est copié.

## Sources officielles

Le manifest fourni identifie six originaux ; cette liste en conserve uniquement le nom de fichier, pas les chemins personnels. `unresolved` signifie non distribué dans ce dépôt et non récupérable automatiquement en CI, même lorsqu’un extrait local a été lu.

- **S01** — 2026 Présentation de la certification DEVIA (SIMPLON) (1) (1).pptx ; extrait `01.txt`. Texte fourni lu ; original externe non distribué. Pages imprimées sauf slides S01.

- **S02** — RNCP37827 Développeur en intelligence artificielle - Simplon (1) (1).pdf ; extrait `02-ocr.txt`. OCR incertain, pagination non fiable, non utilisé pour trancher une exigence.

- **S03** — [Dev IA - titre 2023] Referentiel Activites Compétences et évaluation (7) (1).pdf ; extrait `03.txt`. Texte fourni lu ; original externe non distribué. Pages imprimées sauf slides S01.

- **S04** — Règlement général  de certification Dev IA Simplon (1).pdf ; extrait `04.txt`. Texte fourni lu ; original externe non distribué. Pages imprimées sauf slides S01.

- **S05** — [Dev IA - titre 2023] Règlement spécifique — Version Partenaires (3) (1).pdf ; extrait `05.txt`. Texte fourni lu ; original externe non distribué. Pages imprimées sauf slides S01.

- **S06** — [Dev IA - titre 2023] Grille individuelle d'évaluation (7) (1).pdf ; extrait `06.txt`. Texte fourni lu ; original externe non distribué. Pages imprimées sauf slides S01.

S06 p.2–22 pilote les citations de critères ; S03 p.1–23 confirme leur portée. S04 p.5–6 règle transmission et validation ; S05 p.6–12 règle épreuves/modalités. S01 slides 7–12 contient des contradictions de minutage : arbitrage humain requis, voir conducteur. S02 OCR n’est pas arbitre. Les images des annexes S05 p.15–17 ne sont pas lisibles dans l’extraction texte : non auditées visuellement.

## Preuves du dépôt et compléments externes

Les commandes historiques sont celles rapportées par les documents, **pas des commandes exécutées dans cet audit**, sauf P01 et commandes de lecture Git. Toute commande nécessitant une stack exige une préparation isolée autorisée ; aucun secret ne doit être affiché. `observed_commit` pour X/L désigne HEAD lors de la lecture, jamais le commit de création du fichier externe.


### P01 — preuve vérifiée localement

- Source : `scripts/certification/data_demo.py`; `tests/test_certification_data_demo.py`; `docs/certification/data-evidence.md`. Section : Reproduction hors réseau.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `resolved`.
- Commande / examen : `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_certification_data_demo.py -v`.
- Portée et limites : 5 tests exécutés dans ce worktree : CSV/JSON synthétiques, SQLite temporaire, validation Pydantic Site ; ni HTTP ni PostgreSQL ni big data. 5 lignes, 3 importées ; aucun compte industriel.
- Prochaine preuve : Extraction autorisée et relecture applicative persistée.


### P02 — configuration non vérifiée

- Source : `docs/certification/governance-proposal.md`; `db/init.sql`. Section : Modèle conceptuel partiel ; Registre de travail.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `resolved`.
- Commande / examen : `git show 59a4846b:docs/certification/governance-proposal.md`.
- Portée et limites : Modèle conceptuel partiel et registre proposés ; schéma initial seul insuffisant, migrations nécessaires. Aucune approbation RGPD ni purge exécutée.
- Prochaine preuve : Modèle complet, registre, durées et procédures approuvés.


### P03 — configuration non vérifiée

- Source : `docs/certification/acceptance-plan.md`; `backend/app/main.py`; `backend/app/security.py`. Section : Contrôle C5 ; Parcours et histoires proposés.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `resolved`.
- Commande / examen : `git show 59a4846b:docs/certification/acceptance-plan.md`.
- Portée et limites : Plan de recette et code accessibles dans Git ; aucun login HTTP/DB réel exécuté dans ce lot, pas de couverture OpenAPI exhaustive vérifiée.
- Prochaine preuve : Recette isolée anonyme/authentifiée/intersites/expiration, import-relecture.


### P04 — incomplet

- Source : `docs/certification/benchmark-watch.md`. Section : Sources effectivement lues ; Organisation proposée.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `resolved`.
- Commande / examen : `git show 59a4846b:docs/certification/benchmark-watch.md`.
- Portée et limites : Comparaison préparatoire ; sources locales et fetch primaires historiquement échoués ; aucune veille collective reconstituée.
- Prochaine preuve : Sources primaires recoupées, comparaison sur besoin et partage réellement réalisé.


### P05 — historique

- Source : `docs/certification/model-delivery.md`; `scripts/package_process_drift.py`; `.github/workflows/model-delivery.yml`. Section : Vérification et portée certification.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `resolved`.
- Commande / examen : `python -m pytest -q tests/test_process_drift.py tests/test_model_artifact_compatibility.py tests/test_training_scripts.py tests/test_model_delivery.py`.
- Portée et limites : 28 tests historiques rapportés, pas rejoués ici ; candidat synthétique local, workflow manuel non exécuté dans ce lot, aucune promotion. Split sans purge explicite de l’horizon futur.
- Prochaine preuve : Run autorisé de la chaîne modèle, artefact et cible identifiés, validation temporelle.


### P06 — historique

- Source : `docs/certification/operations.md`; `deploy/monitor-local.py`; `deploy/deploy-pilot.sh`; `backend/app/metrics.py`. Section : Reproduction locale isolée et résultats.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `resolved`.
- Commande / examen : `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -o addopts='' tests/test_operations_local.py tests/test_delivery_workflow.py`.
- Portée et limites : 19 tests et calcul synthétique rapportés historiquement ; Docker factice pour rollback, fichier local firing/resolved, pas destinataire humain ni métriques scorer vivant. Aucun déploiement rejoué ici.
- Prochaine preuve : Chaîne scorer/collecteur/restitution et alerte reçue ; migration/rollback réels autorisés.


### P07 — historique

- Source : `docs/certification/verification-integration.md`. Section : Résultats réels.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `resolved`.
- Commande / examen : `git show 556380d8:docs/certification/verification-integration.md`.
- Portée et limites : Rapport de consolidation au commit 556380d8, base 01fcb4fa ; résultats locaux historiques et mocks/mode démo distincts des E2E DB/Redis. Totaux non additionnés et non transférés à main actuel.
- Prochaine preuve : Recette navigateur→login→API→DB→modèle et contrôles manuels.


### P08 — historique

- Source : `docs/certification/incident-e2e.md`; `tests/e2e/test_cases/test_schema_init.py`. Section : Diagnostic et résolution ; Vérification après correction.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `resolved`.
- Commande / examen : `python3 tests/e2e/run_tests.py -t 1,2`.
- Portée et limites : Incident local : registre schema_migrations préservé, fixtures site/config corrigées ; 54 passed/2 skipped rapportés, non rejoués. Pas attribution certaine au run 33972910378 (logs 403).
- Prochaine preuve : Reproduction avant/après archivée expurgée et lien outil de suivi ; expliquer contribution personnelle.


### P09 — preuve vérifiée localement

- Source : `docs/certification/hdt-candidates.md`; `models/hdt/catalog.json`; `ml/hdt_registry.py`. Section : Périmètre et contrat ; Identités scientifiques.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `resolved`. Trace : PR #1 (revue signalée ; contenu de discussion non relu ici).
- Commande / examen : `git show -s --format=%s 59a4846b ; git show 59a4846b:models/hdt/catalog.json`.
- Portée et limites : PR #1 fusionnée 59a4846b : vraie trace de revue de code du catalogue API, pas coordination collective historique. Catalogue documentaire seulement ; exports recherche non distribués, aucun changement du modèle servi.
- Prochaine preuve : Archiver revue expurgée et contrôler modèle réellement chargé sur cible.


### P10 — configuration non vérifiée

- Source : `.github/workflows/ci.yml`; `.github/workflows/delivery.yml`. Section : .
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `resolved`. Trace : CI 34360646172 ; Delivery 34361237874.
- Commande / examen : `git show 59a4846b:.github/workflows/ci.yml ; git show 59a4846b:.github/workflows/delivery.yml`.
- Portée et limites : YAML versionnés, CI 34360646172 success et Delivery 34361237874 failure signalés et corroborés par P11, non interrogés à distance dans ce lot. Build Web échoué, deploy skipped ; publication API partielle possible.
- Prochaine preuve : Run après fusion du correctif autorisée, images et cible réellement contrôlées.


### P11 — historique

- Source : `docs/certification/ci-delivery-reporting.md`; `tests/test_delivery_reporting.py`; `frontend/scripts/check-build-context.mjs`. Section : État public constaté ; Build Web.
- Commit observé : `4b6b458daa3abe06e5cec0a29ea01543d8411783` ; résolution : `resolved`.
- Commande / examen : `python -m pytest -q tests/test_delivery_workflow.py tests/test_delivery_reporting.py ; cd frontend && npm run test:build-context`.
- Portée et limites : BRANCHE NON FUSIONNÉE fix/delivery-status-report : tests rapport/bash et vrai build Docker local rapportés. Ne rend pas Delivery historique verte. Erreur TS2307 reproduite localement ; logs distants complets 403, causalité unique distante non établie.
- Prochaine preuve : Revue/fusion autorisée puis Delivery liée au nouveau SHA.


### P12 — historique

- Source : `docs/certification/data-c1-c2.md`; `scripts/certification/extract_sources.py`. Section : Exécutions réellement observées ; Analytique locale et big data.
- Commit observé : `54156891db472c26f69cb2701f02ea0639ae7858` ; résolution : `resolved`.
- Commande / examen : `git show 54156891:docs/certification/data-c1-c2.md`.
- Portée et limites : BRANCHE NON FUSIONNÉE feat/certification-data-sources au snapshot 54156891, en correction : HTTP public auxiliaire et projection PostgreSQL rapportés ; ni source industrielle ni big data exécuté. Pas audit de sécurité de son code dans ce lot.
- Prochaine preuve : Attendre commit corrigé revu, réexécuter puis intégrer explicitement ; Spark réel autorisé.


### P13 — historique

- Source : `docs/certification/summary6-runtime.md`; `ml/summary6/runtime.py`. Section : Tests et limites explicites.
- Commit observé : `ea54dc70d52eddaf2c04fa4932fa4aef494a2267` ; résolution : `resolved`.
- Commande / examen : `git show ea54dc70:docs/certification/summary6-runtime.md`.
- Portée et limites : BRANCHE NON FUSIONNÉE feat/summary6-replay, moteur ea54dc70 : paquet privé, 20 tests rapportés avec paquet, 18/2 skipped sans paquet ; API en chantier hors snapshot. Aucun runtime summary6 main ou livrets. Golden borné, pas confirmation terrain.
- Prochaine preuve : Intégration API causale, paquet approuvé, tests et revue ; aucune activation implicite.


### X01 — historique

- Source : `Preuve-manquante/donnees/README.md`. Section : Document lu en lecture seule.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `unresolved`.
- Commande / examen : `Lecture seule du document ; aucune commande productrice rejouée.`.
- Portée et limites : ERP six lignes synthétiques ; repository/session simulés ; SQL contextuelle non exécutée. Empreinte de fichier observé, commit de production inconnu ; absent de la distribution Git.
- Prochaine preuve : Sélectionner extrait expurgé autorisé et vérifier provenance avant annexe de session.


### X02 — historique

- Source : `Preuve-manquante/modele/README.md`. Section : Document lu en lecture seule.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `unresolved`.
- Commande / examen : `Lecture seule du document ; aucune commande productrice rejouée.`.
- Portée et limites : 90 lignes agrégées historiques, pas réentraînement ; package historique distinct des candidats. Empreinte de fichier observé, commit de production inconnu ; absent de la distribution Git.
- Prochaine preuve : Sélectionner extrait expurgé autorisé et vérifier provenance avant annexe de session.


### X03 — historique

- Source : `Preuve-manquante/exploitation/C21-incident-modele.md`. Section : Document lu en lecture seule.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `unresolved`.
- Commande / examen : `Lecture seule du document ; aucune commande productrice rejouée.`.
- Portée et limites : DEMO-MODELE-001 : refus de fixture incompatible et rétablissement ; aucun correctif créé. Empreinte de fichier observé, commit de production inconnu ; absent de la distribution Git.
- Prochaine preuve : Sélectionner extrait expurgé autorisé et vérifier provenance avant annexe de session.


### X04 — historique

- Source : `output/presentation-iddrv-v6/Sources_et_coherence.md`. Section : Document lu en lecture seule.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `unresolved`.
- Commande / examen : `Lecture seule du document ; aucune commande productrice rejouée.`.
- Portée et limites : Renvois D/R, archives de machines distinctes ; pas exécution actuelle. Empreinte de fichier observé, commit de production inconnu ; absent de la distribution Git.
- Prochaine preuve : Sélectionner extrait expurgé autorisé et vérifier provenance avant annexe de session.


### X05 — historique

- Source : `output/presentation-iddrv-v6/Preuves_a_preparer.md`. Section : Document lu en lecture seule.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `unresolved`.
- Commande / examen : `Lecture seule du document ; aucune commande productrice rejouée.`.
- Portée et limites : Préparation historique 75+10, conflit avec S05 p.12 80+10 à arbitrer ; pas réalisation. Empreinte de fichier observé, commit de production inconnu ; absent de la distribution Git.
- Prochaine preuve : Sélectionner extrait expurgé autorisé et vérifier provenance avant annexe de session.


### L1 — historique

- Source : `tmp/coherence-audit/L1_E1_collecte_stockage_mise_a_disposition_C1-C5.txt`. Section : Pages physiques sélectionnées : début et synthèse ; L5 p.1–4.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `unresolved`.
- Commande / examen : `Lecture sélective des extractions ; PDF original non rendu visuellement ici.`.
- Portée et limites : Extraction avec ligatures altérées. Commit de rédaction inconnu. Aucune validation attribuée au texte ; pas copie publique du contenu personnel.
- Prochaine preuve : Vérifier page originale et intégration autorisée du complément ; ne pas réécrire le dépôt historique.


### L2 — historique

- Source : `tmp/coherence-audit/L2_E2_veille_benchmark_parametrage_IA_C6-C8.txt`. Section : Pages physiques sélectionnées : début et synthèse ; L5 p.1–4.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `unresolved`.
- Commande / examen : `Lecture sélective des extractions ; PDF original non rendu visuellement ici.`.
- Portée et limites : Extraction avec ligatures altérées. Commit de rédaction inconnu. Aucune validation attribuée au texte ; pas copie publique du contenu personnel.
- Prochaine preuve : Vérifier page originale et intégration autorisée du complément ; ne pas réécrire le dépôt historique.


### L3 — historique

- Source : `tmp/coherence-audit/L3_E3_api_modele_integration_mlops_C9-C13.txt`. Section : Pages physiques sélectionnées : début et synthèse ; L5 p.1–4.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `unresolved`.
- Commande / examen : `Lecture sélective des extractions ; PDF original non rendu visuellement ici.`.
- Portée et limites : Extraction avec ligatures altérées. Commit de rédaction inconnu. Aucune validation attribuée au texte ; pas copie publique du contenu personnel.
- Prochaine preuve : Vérifier page originale et intégration autorisée du complément ; ne pas réécrire le dépôt historique.


### L4 — historique

- Source : `tmp/coherence-audit/L4_E4_application_ia_conduite_livraison_C14-C19.txt`. Section : Pages physiques sélectionnées : début et synthèse ; L5 p.1–4.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `unresolved`.
- Commande / examen : `Lecture sélective des extractions ; PDF original non rendu visuellement ici.`.
- Portée et limites : Extraction avec ligatures altérées. Commit de rédaction inconnu. Aucune validation attribuée au texte ; pas copie publique du contenu personnel.
- Prochaine preuve : Vérifier page originale et intégration autorisée du complément ; ne pas réécrire le dépôt historique.


### L5 — historique

- Source : `tmp/coherence-audit/L5_E5_monitorage_resolution_incident_C20-C21.txt`. Section : Pages physiques sélectionnées : début et synthèse ; L5 p.1–4.
- Commit observé : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a` ; résolution : `unresolved`.
- Commande / examen : `Lecture sélective des extractions ; PDF original non rendu visuellement ici.`.
- Portée et limites : Extraction avec ligatures altérées. Commit de rédaction inconnu. Aucune validation attribuée au texte ; pas copie publique du contenu personnel.
- Prochaine preuve : Vérifier page originale et intégration autorisée du complément ; ne pas réécrire le dépôt historique.
