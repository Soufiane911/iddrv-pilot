# Summary6 — durcissement API après revue

Ce document **supplante** les paragraphes défaut/rollback, readiness, admission
et nettoyage de [summary6-replay.md](summary6-replay.md). Ce dernier et
[summary6-runtime.md](summary6-runtime.md) restent les preuves de l'état antérieur,
pas une description du nouveau défaut. Aucun changement du cœur `ml/summary6`,
repackaging, recalibration, changement scientifique ou activation live.

## Migration fail-closed

`HDT_RUNTIME_MODE` absent, vide ou inconnu donne désormais `active_mode=disabled`.
Seules les valeurs explicites `summary6_replay` et `historical` sont exécutables.
Le POST historique répond 409 hors rollback explicite. Les gardes existantes de
claim/score/finish/recalculation héritent de ce défaut avant I/O ; le collecteur
peut conserver les observations sans créer de jobs de scoring. Aucun ancien
job n'est réétiqueté et aucun backfill n'est fabriqué.

Arrêter les workers historiques et attendre les transactions avant une bascule ;
redémarrer API, collecteur et scorer avec une configuration cohérente. Les anciens
processus déjà démarrés ne changent pas d'environnement magiquement. Rollback :
arrêt coordonné, `HDT_RUNTIME_MODE=historical` explicite partout, redémarrage.
Les fixtures de tests historiques déclarent maintenant ce mode localement.
Seul `deploy/compose.refonte-test.yml`, environnement legacy dédié aux tests,
le fixe à historical ; Compose général/pilot et `.env.example` utilisent disabled.
Les Compose généraux ne constituent toujours pas une image summary6 certifiée.

Paquet privé durable approuvé, inchangé :

    export SUMMARY6_PACKAGE_DIR=/Users/soufianehamzaoui/.local/share/iddrv/summary6/0c8b4c15cd4df33784468dfcd2057b52261122a8c90dbb0b1ba4a117b2870702
    export SUMMARY6_MANIFEST_SHA256=919fc41c58d1e821f9dcf7e16ee6c317e5966d4ec1c2444ad96045289543f4ff
    bash scripts/launch_summary6_replay.sh

Ces variables restent serveur uniquement. Le lanceur impose **un processus API**,
loopback, préflight avant uvicorn. Configurer aussi DB/auth comme auparavant.

## Contrats et charge

- Handler partagé de validation : enveloppe `error` et request ID préservés ;
  `details.errors` conserve type/loc/msg, retire input/ctx (valeurs non finies,
  objets exceptions et corps potentiellement sensibles). NaN, Infinity, 1e309
  et entiers de 400 chiffres testés en corps/query : 422, pas 500.
- site_id summary6 borné à un entier signé 64 bits positif. Aucune modification
  des autorisations ni conversion permissive des champs stricts.
- Readiness vérifie le manifeste et les SHA des **six gzip**, pas seulement
  l'existence du catalogue. Tous sont revérifiés avant chaque replay ; le fichier
  sélectionné est aussi vérifié sur les octets effectivement décodés. Aucun
  cache readiness/modèle ne peut cacher un remplacement après un premier succès.
  `/current` garde son contrat 200 avec `not_ready`/raisons sûres ; replay 503,
  lancement interrompu si un fichier est absent ou corrompu.
- Quota de calcul simultané : **1 par user_id authentifié, 2 au total par
  processus**, partagé entre `/current` et `/replay`. Aucun ID du payload ou de
  session n'est utilisé ; rejet immédiat 429 avec `Retry-After: 1`, avant modèle.
  Libération en finally même si le moteur échoue. La table contient uniquement
  les identités actives, au plus deux, supprimées immédiatement à la sortie.
  Aucune métrique à label identité ni fuite supplémentaire de pin/chemin.
- Pas de cache de modèle, pas de file d'attente infinie, pas de quota cumulatif
  temporel : il s'agit d'une admission concurrente, pas d'une limite req/min.
  **Un seul processus/réplica est le périmètre pris en charge par ce profil.**
  Plusieurs workers/réplicas multiplieraient la limite ; une admission distribuée
  serait nécessaire avant une telle extension. Les limites ne couvrent pas
  l'ensemble des autres API ni le volume réseau des corps invalides.

## Smoke jetable et vérifications exécutées

Le smoke vérifie paquet et six fichiers **avant Docker/réseau**. Conteneur UUID
et label propriétaire, image déjà présente (`--pull=never`), stockage tmpfs,
ports loopback libres, pas de volume partagé. Nettoyage : terminate, attente,
kill puis attente si timeout ; finally indépendant pour connexion et conteneur,
même si l'arrêt API échoue. Inspect du label puis suppression par ID uniquement
si propriétaire correspondant. Aucun nettoyage global ou par préfixe.

Commande : `python scripts/smoke_summary6_local.py` avec les deux variables
ci-dessus. **PASS exécuté sur le nouveau pin** : véritable HTTP/login DB,
401 sans session, 403 autre site, cutoffs 59/79/83/84/399, aucun incident ajouté.
Décisions : null, null, 0.42204178647765367 (abstention),
0.4179955185182244 (available), 0.455445834063937 (available).
Le conteneur créé a été supprimé. Pas de téléchargement ni stack partagée.

Suite Python, paquet réel configuré via `SUMMARY6_TEST_PACKAGE` et
`SUMMARY6_TEST_MANIFEST_SHA256` :

    python -m pytest -q --ignore=tests/e2e

**528 passed, 37 skipped**, aucun échec. Les skips correspondent notamment aux
intégrations DB externes non configurées ; aucun test e2e destructif lancé.
Tests ajoutés : middleware/handlers de production exacts dans TestClient,
non-finitude/overflow, modes absent/inconnu, six fichiers endommagés après
readiness positive, préflight sans réseau, moteur lent concurrent, refus avant
loader, libération sur exception et éviction mémoire, timeout/kill et propriété
du conteneur. Les tests auth TestClient conservent leur repository session stub.

Ce n'est ni une certification navigateur ni une migration/connexion live, ni
une validation scientifique supplémentaire. Les preuves frontend relèvent du
rapport distinct. Aucun commit/stage/push effectué pendant ce travail parallèle.
