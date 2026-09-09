# CI et compte rendu de livraison

## État public constaté

Consultation en lecture seule de l’API publique GitHub (runs, jobs et annotations), sans authentification. HEAD local et main distant : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a`, fusion PR #1 catalogue (`31c8c2c2`). Aucun AGENTS.md trouvé dans le worktree ni ses répertoires parents.

- [CI main 34360646172](https://github.com/Soufiane911/iddrv-pilot/actions/runs/34360646172) : **success**, six jobs réussis, dont frontend, Playwright, Compose et E2E.
- [CI catalogue 34359776838](https://github.com/Soufiane911/iddrv-pilot/actions/runs/34359776838) : **success**.
- [Delivery main 34361237874](https://github.com/Soufiane911/iddrv-pilot/actions/runs/34361237874) : **failure réelle**, build/push Web échoué, deploy skipped, rapport échoué. Annotation job `102498458030` : `npm run build` dans Docker termine avec code 2. L’étape API a réussi : une publication partielle est possible, ne pas affirmer qu’aucune image n’a été publiée. Ce correctif ne rend pas cette livraison verte.
- [CI antérieure 34358036273](https://github.com/Soufiane911/iddrv-pilot/actions/runs/34358036273), SHA `82da50c0` : frontend **Run tests failure**. Annotation `frontend/src/test/workshopSetup.test.tsx:62` : attendu `erp_ref: ERP-608`, reçu `erp_ref: null`, `name: Presse sans ERPERP-608`. Cela localise une saisie reçue dans le champ nom plutôt que la référence ; la cause racine (focus, sélecteur, concurrence ou autre) n’est pas démontrée.
- [Delivery antérieure 34358311023](https://github.com/Soufiane911/iddrv-pilot/actions/runs/34358311023) : build et deploy **skipped**, mais rapport **failure**. Défaut reproduit par le chemin shell original qui exigeait build success avant d’examiner la CI amont.

Les téléchargements `/actions/jobs/{id}/logs` retournent **HTTP 403** sans authentification. Les annotations ne suffisent pas à expliquer l’échec Docker ni à certifier une cause de flakiness frontend. Aucun changement CI/frontend ni affaiblissement des tests.

## Contrat corrigé

`.github/workflows/delivery.yml`, uniquement le job `deployment-status` :

| CI | Build/push | Deploy | Rapport |
|---|---|---|---|
| non réussie, notamment failure/cancelled | skipped | skipped | Informatif, aucune livraison tentée, pilote non déployé |
| quelconque | failure/cancelled ou deploy failure/cancelled | quelconque | Échec conservé, publication partielle possible, aucun succès de déploiement revendiqué |
| success | success | skipped, promotion désactivée | Images publiées, pilote non déployé |
| success | success | success | Succès du job de déploiement au SHA validé |
| autre combinaison | | | Échec explicite pour état inattendu |

Les résultats effectifs des jobs priment sur la variable de promotion : une erreur de déploiement n’est jamais transformée en absence de promotion. Les valeurs GitHub passent par `env`, puis des expansions shell citées et `printf '%s'`, jamais par interpolation d’expressions dans le script. Le même texte est écrit dans les logs et `GITHUB_STEP_SUMMARY`. Les permissions, publications et commandes SSH restent inchangées.

Un rapport informatif réussi après une CI échouée n’est pas une CI verte ni une preuve de déploiement. Le seul message positif exige les trois résultats success. Il atteste le résultat du job SSH existant, pas une nouvelle certification fonctionnelle indépendante du pilote. Une annulation du workflow Delivery lui-même peut empêcher l’exécution du rapport malgré `always()` ; les tests ne simulent pas l’ordonnanceur GitHub.

## Vérification locale sans effets distants

- `python -m pytest -q tests/test_delivery_workflow.py tests/test_delivery_reporting.py` : 201 tests réussis.
- `python -m pytest -q tests --ignore=tests/e2e` : 635 réussis, 37 ignorés.
- Validation des trois YAML via `yaml.safe_load` local : OK ; `bash -n` du script inclus dans les tests ; `git diff --check` : OK. `actionlint` absent, validation sémantique GitHub non exécutée.

`tests/test_delivery_reporting.py` exécute le vrai bloc bash du rapport avec des contextes GitHub explicitement simulés : matrice 4×4×4×3 (success/failure/cancelled/skipped, promotion true/false/vide), vérification du câblage workflow_run/needs, résumé, codes retour et injections shell dans chacun des cinq champs. Aucun build, réseau, Docker ou SSH dans ces tests. Pas de nouvelle dépendance de test.

Aucun push, workflow déclenché, publication d’image, déploiement, accès aux secrets ou modification des permissions. Le correctif doit être revu puis validé par un futur run autorisé ; l’échec Docker Web existant reste à investiguer avec les logs accessibles à un mainteneur.
