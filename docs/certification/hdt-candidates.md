# Catalogue HDT v1 — ajout documentaire, PAS inférence

Base d’implémentation vérifiée : `82da50c094578333d18897beb2f74eebe95f9de7`.

## Périmètre et contrat

`models/hdt/catalog.json` est l’unique source versionnée. `ml/hdt_registry.py`
valide le JSON (schéma fermé, un seul défaut historique, IDs uniques, SHA256,
chemins relatifs sous `models/` ou `output/`, statuts et distribution cohérents).
Les références sont documentaires : le registre ne les ouvre jamais et ne
charge aucun pickle. Aucun import runtime depuis `output/`, aucune migration.

`GET /api/v1/process-drift/candidates` requiert une session, avec les mêmes rôles
que le POST historique : viewer, analyst, supervisor, admin. Métadonnées globales
non rattachées à un site; pas de données terrain. Réponse = catalogue validé;
401 sans authentification, 503 générique si catalogue illisible/invalide, sans
chemins privés. Aucun paramètre de chemin ou de sélection n’est accepté/utilisé.
Le catalogue est inclus par le `COPY models` déjà présent dans l’image backend.

POST, chargeur historique, worker, prédictions, épisodes et métriques live ne
changent pas. Le champ `default` décrit le défaut applicatif, il ne le configure
pas. `executable` décrit uniquement le paquet historique connu; ce n’est pas une
attestation de disponibilité du modèle dans un déploiement donné. Monitoring
sépare cette référence de la version réellement retournée par chaque inférence
du simulateur. Aucune carte « gagnant », sélection ou activation de recherche.

## Identités scientifiques

| Entrée (jeu/graine de l’export) | Statut et limites |
|---|---|
| Historique release `29dea3dca96a` | Seul paquet distribué/exécutable, défaut inchangé. Dataset et graine originaux non vérifiés, non inventés. |
| Summary6 `61007/42`, `f70c137b944a` | Recherche uniquement; confirmation initiale 5 jeux61007–61011, 3 graines, 90 épisodes distincts. Rappel utile51.5%, FP6.11/1000; plafond dépassé sur61008 (14.18). |
| Mean79/PCA16 `61042/42`, `31234bda9fd4` | Challenger bloqué. Confirmation01: 50 jeux61042–61091, 900 épisodes; rappel61.15% contre summary6 55.81% dans cette même population. Plafond FP échoué7/50, pire18.401 malgré moyenne6.004. |
| EWM20 shrink75 budget0.0026 `61032/42`, `894120d3ac76` | Dernier candidat sélectionné **en développement**, export **smoke-only sur ancien jeu**. Confirmation02 **absente**, jeux61092–61141 non générés (blocage disque enregistré). |

EWM20: développement60 jeux61032–61091, rappel58.4259%, FP2.5590/1000,
pire8.7318; sous-population50 récents rappel58.8519%, FP2.7356. Ce ne sont pas
110 jeux indépendants. Les anciens jeux de confirmation01 sont réutilisés :
aucune comparaison confirmatoire indépendante avec mean79. Le choix minimise
le pire FP parmi les candidats admissibles, pas le rappel maximal. Le champ
source `development_only=False` et le nom `hdt-fixed-confirmation-attempt2`
ne priment pas sur `smoke=True`. Aucun « meilleur production » établi.

Les trois exports recherche sont **référencés mais NON distribués** :
`distribution=source_only`, `artifact_packaged=false`, exécution interdite.
Ils ne remplacent pas `models/process_drift_hdt_v1.joblib`. Un export = un jeu et
une graine, pas toutes les forêts d’une campagne ni un ensemble de graines.
Les populations évaluées et leurs trois graines sont distinctes de cet export.

## Provenance et vérification

Les SHA complets de chaque artefact et rapport sont dans le JSON. Ils ont été
recalculés sur les octets des sources en lecture seule, sans désérialisation;
les quatre SHA d’artefacts et le gel summary6 ont aussi été comparés aux SHA de
l’identification préalable. Les sources `output/` restent hors distribution;
leur absence sur un serveur applicatif n’empêche pas de consulter le catalogue.
Les tests revérifient les fichiers historiques distribués, pas des campagnes
privées absentes de CI. Les versions recherche seules ne sont pas des IDs
immutables; l’ID catalogue inclut représentation/politique, jeu, graine et
préfixe SHA de l’export (inventaire release pour l’historique).

Empreintes des rapports principaux recalculées :

- Summary6 `output/hdt-feature-hypotheses-2026-09-07/REPORT.md` :
  `451458d1eb9a68159969499b0bf0cb51c8115f872c18933eef820e7c19250777`.
- Mean79 `output/hdt-adaptive-search-2026-09-08/CONFIRMATION01-REPORT.md` :
  `aa0129a6cac912660216693e7aee692678366fa3d64575bbbd3079d29345e692`.
- EWM20 `output/hdt-adaptive-search-2026-09-08/DEV20-21-BUDGET-RESULTS.md` :
  `bb441b0050f8a40724c8b41b79d486e7d63a8a9a505bc35687b633c1000e1eb9`.
- Smoke `output/hdt-adaptive-search-2026-09-08/confirmation02-smoke-dev61032/SMOKE-AUDIT.json` :
  `33984f07ec503a82c7d4db79055b08095c1831bcd6cf6ba1a1bb0517fddaf101`.

Pour ajouter une entrée : créer une nouvelle identité (ne pas réaffecter un ID
existant à d’autres octets/politique), relever SHA et preuves, expliciter phase,
population/unité, contrat causal et blocages, puis lancer les tests. Changer un
statut recherche en exécutable exige une nouvelle tranche de conception : le
registre v1 le refuse délibérément. Il ne fournit aucun mécanisme d’exécution.

## Prochaine étape obligatoire avant toute exécution

1. Packaging autonome audité : forêt, références, scaler/PCA, prétraitement,
   politique/seuils figés, dépendances et empreintes; aucune classe pickle
   opportuniste importée depuis `output/`. Mean79/EWM20 attendent actuellement
   `ResearchFeatures` et un DataFrame préparé à137 colonnes.
2. Golden replay brut → features → score → min3 → seuil → décision, preuve
   d’équivalence, invariance au futur, tests trous/non-finis/reset/restart.
3. Contexte lot/recette/machine et compteur source fiables, connus à temps;
   préfixe complet du lot jusqu’au cycle79 (lot80), garde20–59, ancre20–79 pour
   les variantes, publication84. Pour EWM `adjust=True`, conserver l’état causal
   depuis20 : ni les20 derniers cycles ni100 cycles arbitraires ne suffisent.
4. Confirmation02 indépendante puis cycles de qualification terrain,
   observabilité séparée, rollout/rollback et isolation des incidents par
   identité. Le catalogue n’autorise ni reprise d’entraînement ni activation live.

## Vérification ciblée

- Python : `python3 -m pytest -q tests/test_hdt_registry.py tests/test_process_drift_api.py tests/test_process_drift.py tests/test_model_artifact_compatibility.py tests/test_model_delivery.py tests/test_hdt_scoring_worker.py tests/test_process_drift_monitoring.py`.
- Frontend : `tsc -b`; `vitest run src/test/hdtCandidates.test.tsx src/test/api.test.ts src/test/pages.business.test.tsx`; ESLint sur les fichiers TypeScript modifiés.
- UI testée avec données catalogue versionnées et mocks bornés, états chargement,
  erreur/retry, vide, contrats GET et accès clavier aux détails natifs.
  Pas de validation terrain ni navigateur réel revendiquée.

Résultats dans le worktree : Python **68 passed, 8 skipped**; frontend
**45 passed, 2 skipped**; typecheck et lint ciblé réussis. Les skips sont ceux
des suites préexistantes. Première tentative avec le `.venv` du projet bloquée
à la collecte (numpy/pandas/psycopg2 absents); exécution réussie ensuite avec
l’interpréteur `python3` existant, sans installation. Les dépendances frontend
existantes ont été utilisées par lien temporaire, sans copie massive.
