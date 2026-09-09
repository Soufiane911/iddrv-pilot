# Incident E2E — réinitialisation du schéma et contrats de fixtures

## Périmètre et traçabilité

Investigation locale du 9 septembre 2026, base Git vérifiée :
`01fcb4fa8daa8261ca34cf2e44171a4d7836af5b`.
Signalement : GitHub Actions run `33972910378`, head annoncé `482ba551`,
étape « Run E2E harness ». `gh` absent ; téléchargement public des logs via
`https://api.github.com/repos/Soufiane911/iddrv-pilot/actions/runs/33972910378/logs`
refusé HTTP 403. Les causes ci-dessous sont **reproduites sur la base locale**,
pas attribuées avec certitude au run distant dont les journaux restent indisponibles.

## Reproduction isolée

Python 3.13.9 et dépendances déjà disponibles, aucune installation.
Deux conteneurs créés exclusivement pour cette investigation :
`iddrv-cert-e2e-f7bb-pg` (TimescaleDB `2.28.2-pg16`, PGDATA en tmpfs),
`iddrv-cert-e2e-f7bb-redis` (Redis `7-alpine`, persistance désactivée).
Ports publiés uniquement sur 127.0.0.1 : 57603 et 57604, choisis initialement
par Docker. Base `iddrv_test`, Redis DB 1 ; aucun volume utilisateur monté.
Confirmation destructive et sentinelles du harness conservées.

Commande (mot de passe temporaire transmis par environnement, omis ici) :

```sh
export E2E_DATABASE_URL='postgresql://iddrv_user:<temporaire>@127.0.0.1:57603/iddrv_test'
export E2E_REDIS_URL='redis://127.0.0.1:57604/1'
export E2E_DESTRUCTIVE_CLEANUP_CONFIRMATION='iddrv_test:truncate-and-redis-1:flush'
python3 tests/e2e/run_tests.py -t 1,2
```

Ne pas réutiliser ces ports sur une stack inconnue : provisionner d'abord ses
propres conteneurs éphémères, vérifier les ports et adapter les URL.

Avant correction : **11 échecs, 43 succès, 2 ignorés**, code 1 (35,19 s).

## Diagnostic et résolution

1. Six tests loader inséraient `machines(erp_ref,name)` sans `site_id` :
   `NotNullViolation`, avant même l'appel du loader. Les fixtures précisent
   désormais le site 1, identique au `--site-id 1` utilisé par le loader.
   La contrainte de production reste inchangée.
2. Le test du détecteur patchait `backend.app.db.settings`, attribut inexistant
   depuis l'utilisation de `config.settings` dans la connexion DB :
   `AttributeError`. Le patch cible désormais `backend.app.config.settings`.
   Les assertions « une insertion puis zéro doublon » sont conservées.
3. Le nettoyage automatique tronquait **schema_migrations**, mais conservait
   les objets SQL. `setup_db.py`, qui applique les migrations immuables une
   seule fois via leur registre/checksum, rejouait donc les anciennes migrations.
   La 006 échouait en supprimant une PK référencée par des FK ultérieures.
   Une hypothèse de correction SQL conditionnelle a révélé ensuite la création
   répétée de `machine_connections` en 014 ; cette modification SQL a été
   entièrement annulée : c'était le registre effacé, pas la migration, la cause.
   Le nettoyage exclut maintenant `schema_migrations`, comme les sentinelles.
   Aucun `CASCADE` supplémentaire, aucune migration ni code production modifié.

Le test d'idempotence vérifie désormais que toutes les migrations attendues
sont enregistrées **après nettoyage**, puis que noms, checksums et dates
restent identiques après deux setups. Les assertions existantes ne sont pas
assouplies. La CI conserve les rapports JSON/TXT expurgés par le harness via
`upload-artifact`, même après échec ; un échec précoce sans rapport reste possible.

## Vérification après correction

La base temporaire affectée par les essais a été recréée, uniquement en
supprimant/recréant le conteneur de cette investigation.

- Harness complet tiers 1,2 : **54 succès, 2 ignorés**, code 0, 38,92 s.
- Nouveau passage après renforcement du test de registre : **54 succès,
  2 ignorés**, code 0, 39,10 s (vérifie aussi un redémarrage du harness).
- `python3 -m pytest -q tests/e2e/test_safety_guards.py`, mêmes URL isolées :
  **7 succès**, 0,79 s.
- `git diff --check` : réussi.

Les deux tests ignorés préexistants nécessitent respectivement
`ERP_TEST_DATABASE_URL` et `TELEMETRY_TEST_DATABASE_URL` ; ils n'ont pas été
activés. Pas de preuve de leur succès. Journaux locaux de cette session :
`/tmp/iddrv-e2e-before.log`, `/tmp/iddrv-e2e-after.log`,
`/tmp/iddrv-e2e-final.log` (éphémères, non versionnés).
Les deux conteneurs dédiés ont été supprimés nommément après vérification ;
aucun prune, aucun arrêt d'une stack utilisateur, aucun accès production.

## Apport et limites certification

Le référentiel officiel, C21 (page 23/25, extrait `03.txt`), demande causes,
reproduction, procédure de débogage, solution documentée et versionnement.
Cette fiche et les tests apportent une reproduction réellement exécutée et
une correction limitée, pas une acquisition automatique de compétence.
La version définitive doit être intégrée/versionnée par le parent, avec son
identifiant Git ajouté au dossier de preuve ; aucun push ni validation GitHub
ou jury n'est revendiqué. Le lien avec l'outil de suivi distant et les logs du
run signalé reste à compléter. Les autres jobs CI n'ont pas été rejoués ici.
