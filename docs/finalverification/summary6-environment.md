# Summary6 — environnement et correction CI PR #8

## Cause observée

Run GitHub **34367460585**, base `120d74aaaf0f6df87c9e80ca4c948d42a5f8d995`.
Dans le log expurgé `/tmp/iddrv-pr8-ci-failure.log` :

- Ligne 306 : résolution NumPy **2.5.3**, pandas **3.0.5**, SciPy **1.18.1**, avec sklearn 1.7.2 / joblib 1.5.2.
- Lignes 420–423 : `joblib/numpy_pickle.py:207`, affectation `array.shape`,
  `DeprecationWarning: Setting the shape on a NumPy array has been deprecated in NumPy 2.5.`
- Lignes 5030–5055 : avertissements annexes Starlette/AnyIO et pytest ; la majorité
  des avertissements provient de cette désérialisation joblib.
- Ligne 5157 : **691 passed, 41 skipped, 50 errors, 86786 warnings**, 35 subtests.

`pandas>=2.0` et NumPy/SciPy transitifs non bornés permettaient cette dérive.
Les fixtures tiny créent leur paquet dans l'environnement courant : elles échouent
au chargement strict des warnings, pas à cause d'un paquet privé absent.
Le chargeur doit continuer à traiter les warnings comme fatals.

## Contrat commun d'installation

`constraints-numerical.txt` est l'unique source des pins numériques :
NumPy 2.2.6, pandas 2.3.3, SciPy 1.16.3, scikit-learn 1.7.2, joblib 1.5.2.
Ce n'est pas un lock complet des dépendances HTTP/outillage.

- `requirements.txt` le charge avec `-c constraints-numerical.txt` : ingest local,
  entraînement et packaging via les scripts Python, lint CI.
- `backend/requirements.txt` le charge avec `-c ../constraints-numerical.txt` :
  backend seul, tests CI et workflow model-delivery (pins numériques dupliqués retirés).
- pip résout `-c` relativement au fichier requirements, pas au répertoire courant.
- `backend/Dockerfile` copie le fichier vers `/app/constraints-numerical.txt`
  **avant** l'installation de `/app/backend/requirements.txt`.
  API, worker ingest, collector et scorer partagent cette image ; les compose
  pilote/refonte utilisent également le Dockerfile backend avec contexte racine.
- Aucun requirements ingest indépendant. Les requirements analytiques optionnels
  ne contiennent que DuckDB ; l'image QA press_api seulement FastAPI/Uvicorn ;
  l'image frontend n'installe pas de pile numérique Python.
- `.github/workflows/ci.yml` est inchangé : ses installs existants appliquent ces contraintes.

## Vérifications exécutées localement

Environnement **neuf**, sans site-packages globaux, créé avec le Python 3.13.9
existant uniquement comme interpréteur de base (aucune installation Anaconda/globale) :

```sh
/opt/miniconda3/bin/python3.13 -m venv /tmp/iddrv-pr8-clean-venv
/tmp/iddrv-pr8-clean-venv/bin/python -m pip --isolated install \
  --index-url https://pypi.org/simple --timeout 30 --retries 1 --no-cache-dir \
  -r requirements.txt -r backend/requirements.txt pytest
/tmp/iddrv-pr8-clean-venv/bin/python -m pip check
/tmp/iddrv-pr8-clean-venv/bin/python -m pytest -q tests --ignore=tests/e2e -ra
```

22 GiB disponibles avant installation ; venv final 329 MiB.
`pip check` : aucune dépendance cassée. Environnement constaté : Python **3.13.9**
et les cinq versions ci-dessus. Résolution backend seul également réussie depuis
`/tmp`, avec requirements en chemin absolu, `--dry-run --ignore-installed` et mêmes
options réseau ; les cinq pins restent effectifs.

- Suite backend identique à CI sans paquet privé : **747 passed, 41 skipped,
  2 warnings, 35 subtests passed**. Cela inclut six nouveaux cas de régression
  (résolution réelle par le parseur pip depuis racine/backend, sources CI, copie Docker).
- Suite summary6 runtime/package/API/hardening avec paquet privé approuvé :
  **92 passed, 0 skipped, 1 warning**. Golden exact et comparaison des six modèles
  source/paquet exécutés, sans réentraînement ni remplacement.
- Suite backend complète avec ce même paquet : **750 passed, 38 skipped,
  2 warnings, 35 subtests passed**. Skips : bases d'intégration dédiées absentes
  et DuckDB optionnel absent ; les trois skips privés sont levés.
- Les deux warnings restants concernent Starlette/AnyIO et la paramétrisation
  pytest, pas joblib/NumPy. Aucun warning ni test masqué.
- `git diff --check` réussi ; aucun changement `ml/summary6/*`, modèles,
  données/manifeste replay ou sélection backend. Le chargement réel valide
  également les hashes du code et l'environnement avant désérialisation.

Paquet utilisé : runtime `summary6-0c8b4c15cd4df33784468dfcd2057b52261122a8c90dbb0b1ba4a117b2870702`,
pin manifeste indépendant `919fc41c58d1e821f9dcf7e16ee6c317e5966d4ec1c2444ad96045289543f4ff`.
Il demeure privé hors Git. Traces locales : `/tmp/iddrv-pr8-{install,resolve,full,real,full-real}.log`.

## Correction du comparateur interop — run 34369234541

Base `34e8f0efaa80a21dad1f7ba156ca4929725e967b`. Le log
`/tmp/iddrv-pr8-failure-34369234541.log` (lignes 337–391) rapporte
**746 passed, 41 skipped, un échec** : égalité des features du test tiny,
4 valeurs sur 72, écart absolu maximal `1.11022302e-16`, relatif maximal
`1.34308227e-16`, sous Linux x64 / Python 3.13.15, dépendances épinglées.

Le golden introduit par `ea54dc70` déclare un oracle indépendant : fonctions
figées extraites par AST de `evaluate.make_features`, `hdt_methods.features`
et `feature_study.representations`, export sklearn approuvé, sans utiliser le
code features du runtime ; source SHA256
`f70c137b944a04da6c8f1c405c4b217322019e60d3bb1e5d63066947d9a888ad`,
NumPy 2.2.6 / pandas 2.3.3. Le port `ml/summary6/runtime.py` calcule les
résidus normalisés par médiane d'ancrage / scale, puis moyenne absolue et
écart-type glissants sur 20 cycles (`ddof=0`), réduits sur huit capteurs en
max, RMS (`sqrt(mean(x**2))`) et quantile 0.75. Ces réductions float64
peuvent varier au dernier bit entre builds/architectures ; le log seul ne
permet pas d'attribuer l'écart à une opération précise ni au patch Python.

**Borne retenue : 1 ULP, pas 2.** Mesure sur les 72 valeurs golden : plage
`[0.43745928206432616, 1.314077666699433]`, espacements float64
`{2**-54, 2**-53, 2**-52}`. Deux appels `np.nextafter` dans chaque direction
donnent une distance relative minimale de `2.221179821923171e-16`, supérieure
au maximum relatif publié par CI (`1.34308227e-16`, même avec son arrondi
d'affichage). Cela borne les différences rapportées à un voisin float64 ;
aucune mesure ne justifie d'élargir à 2 ULP. Ce raisonnement utilise le résumé
CI et le golden, pas un nouveau calcul Linux. Sur macOS arm64 / Python 3.13.9,
le calcul avec le paquet approuvé reste mesuré à **0 ULP** sur les 72 valeurs.

Seul le comparateur features du test tiny utilise désormais
`assert_array_max_ulp(..., maxulp=1)`, avec formes identiques et finitude
explicite des deux tableaux ; aucune tolérance relative/absolue large.
16 cas de contrôle acceptent un voisin dans les deux directions et rejettent
2 ULP, une perturbation de ±1e-12, NaN/±inf (y compris identiques des deux
côtés), et une forme diffusable. États, compteurs, causalité, seuils et décisions
restent stricts. Le golden privé et la comparaison source/paquet des six modèles
restent **exacts** dans l'environnement approuvé ; l'interop bornée du tiny
n'assouplit ni le manifeste ni l'environnement de chargement.

Venv isolé ci-dessus réutilisé sans installation. Commande complète :

```sh
SUMMARY6_TEST_PACKAGE=/Users/soufianehamzaoui/.local/share/iddrv/summary6/0c8b4c15cd4df33784468dfcd2057b52261122a8c90dbb0b1ba4a117b2870702 \
SUMMARY6_TEST_MANIFEST_SHA256=919fc41c58d1e821f9dcf7e16ee6c317e5966d4ec1c2444ad96045289543f4ff \
/tmp/iddrv-pr8-clean-venv/bin/python -m pytest -q tests --ignore=tests/e2e -ra
```

Résultat local : **766 passed, 38 skipped, 2 warnings, 35 subtests passed**
(log `/tmp/iddrv-pr8-ulp-full-real.log`). Tests privés exécutés, warnings non
masqués. `git diff --check` réussi. Golden non régénéré, SHA256 inchangé :
`333b3ee422129cd8da3b5b1ab1e14eb2ef4f16fdea889ecb8500530770513d62`.
Aucune modification du code `ml/summary6`, des pins, du paquet ou du manifeste.
Le seul état non suivi préexistant, `frontend/node_modules`, est préservé.
**Correction non encore testée sur GitHub/Linux** : le prochain run CI reste
nécessaire ; aucune preuve d'exécution Linux réussie n'est revendiquée.

## Limites et activation runtime

Le manifeste exige **Python 3.13.9 exactement**, pas simplement 3.13.
CI utilise un patch flottant (3.13.15 dans le run défaillant) ; les tiny tests
sont construits dans ce patch, mais ne prouvent pas la compatibilité du paquet privé.
Le tag Docker conservé `python:3.13-slim` peut lui aussi avancer : les contraintes
pip ne verrouillent pas Python. **Cette correction ne rend pas l'image Docker
summary6 prête à l'emploi.** Aucun build/pull d'image ni disponibilité d'un tag
Python 3.13.9 n'est revendiqué ; aucun test réseau PostgreSQL/Redis ou frontend
n'a été réexécuté dans cette correction ciblée.

L'opérateur doit fournir un runtime Python 3.13.9 vérifié, installer les contraintes,
monter le paquet privé et fournir le pin approuvé avant d'utiliser
`scripts/launch_summary6_replay.sh` (mono-worker). Si le patch diffère, le refus
strict reste requis ; ne pas modifier le manifeste, les hashes ni les warnings
pour contourner ce contrôle. Ces résultats locaux ne sont pas un nouveau run GitHub
et ne constituent pas une validation scientifique/industrielle du modèle.
