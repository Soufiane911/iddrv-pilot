# Exploitation — C11, C19, C20

## Périmètre et niveau de preuve

Base inspectée : `01fcb4fa8daa8261ca34cf2e44171a4d7836af5b`.
Référentiel officiel, extrait `03.txt`, pages 12–13, 21–22 : collecte,
alerte et restitution du modèle, chaîne de livraison exécutée, surveillance
opérationnelle au moins localement. Aucun critère n'est déclaré acquis : la
présence de configuration et les tests ci-dessous ne valent pas validation jury.

Aucun déploiement, push, workflow distant, accès DB, démarrage de conteneur ou
lecture de credentials existants n'a été effectué. Tests Python avec dépendances
déjà installées, sans installation. Aucun volume/stack préexistant touché.

## Défauts corrigés

- Le compose pilote omettait `collector` et `scorer`, nécessaires à la collecte
  télémétrique et au scoring continu ; le watcher de fichiers ne les remplace pas.
  Leurs commandes, variables, dépendance à la migration et heartbeats sont alignés
  sur le compose racine. Image API immuable commune, rôle worker seulement,
  aucun port publié. Origines HTTP interdites par défaut ; allowlist vide par
  défaut. L'API pilote reçoit également les variables d'allowlist télémétrique.
- Le worker pilote n'avait pas de healthcheck : fraîcheur du heartbeat ajoutée.
- `up --abort-on-container-exit ... migrate` pouvait arrêter les dépendances DB
  au terme de la migration. Le script attend désormais DB/Redis, exécute la
  migration seule avec `run --rm --no-deps`, puis attend les services runtime,
  dont collector/scorer, avec `--wait`, et contrôle `/ready`.
- L'ancien script écrasait le tag de retour avant succès. Les tags connus bons
  ne changent désormais qu'après les contrôles ; le pending reste disponible
  après échec. Verrou local contre les exécutions concurrentes.
- Correction P1 : un pending indique une tentative incomplète ; le rollback
  restaure alors `.last-image-tag`, et non `.previous-image-tag`. Avec last=A,
  previous=B, pending=C, il rétablit A et conserve B. Sans pending, le rollback
  normal rétablit B et conserve A comme précédent. Le pending est supprimé
  seulement après succès runtime/readiness ; une récupération échouée peut être
  retentée. Les SHA persistés invalides et une récupération sans last-good sont
  refusés avant Docker, sans inventer de cible.
- Le rollback rejouait les anciennes migrations : il n'en exécute désormais
  aucune, et exige une confirmation explicite de compatibilité du schéma.

## Livraison et retour arrière (procédure, non exécutée)

Le workflow `delivery.yml` existant s'active après succès de CI sur main,
construit/publie les deux images au SHA validé, puis promeut uniquement si
`DEPLOY_ENABLED=true` dans l'environnement pilote. Sans promotion, il indique
« not deployed ». Aucun changement de permissions, secrets ou workflow ici.

Prérequis opérateur : Docker Compose récent supportant `up --wait`, images
accessibles, configuration privée des trois rôles DB distincts, secret session,
HTTPS frontal (cookie sécurisé), allowlist des sources approuvées. Voir
`deploy/README.md` pour les noms de variables ; ne jamais joindre `.env` ou
sortie de `compose config` avec valeurs à une preuve.

Sur un hôte autorisé seulement : `IMAGE_TAG=<SHA40> GHCR_OWNER=<owner>
DEPLOY_PATH=<répertoire-absolu> bash deploy/deploy-pilot.sh`.
Le script attend les dépendances, migre, démarre et vérifie le runtime puis
mémorise le SHA. Un échec laisse une stack potentiellement partiellement mise
à jour : ne pas annoncer une livraison réussie. Lire les logs filtrés, le tag
pending et les healthchecks ; ne pas effacer de volumes.

Avant retour arrière : sauvegarde DB adaptée et vérification de compatibilité
ancienne application/nouveau schéma et contrats d'artefact ; sinon arrêter et
préparer une correction en avant. Avec autorisation et compatibilité prouvée :
`ROLLBACK_SCHEMA_COMPATIBLE=true ... bash deploy/deploy-pilot.sh rollback`.
C'est uniquement un retour d'images, pas une restauration DB/données ni du
manifeste précédent. Ne jamais utiliser `down -v`. Un verrou `.deploy-lock`
laissé par arrêt brutal nécessite vérification de l'absence d'opérateur actif
avant intervention manuelle. Une sauvegarde DB/restauration réelle n'est pas
prouvée par ces tests.

## Métriques, seuils et canal local

`backend/app/metrics.py` expose `/metrics`, protégé par session administrateur
ou token de collecte existant (`X-Metrics-Token`). Aucune ouverture publique ou
désactivation d'auth ajoutée. Requêtes/statuts/latences et disponibilité DB sont
exposés. Les compteurs de prédiction API sont **locaux au processus** : ils ne
mesurent pas automatiquement les prédictions du scorer séparé. Heartbeat frais
signifie boucle vivante, pas source joignable ni modèle performant. L'export
agrégé scorer/feedback et une politique de rétention restent à démontrer.

Le script `deploy/monitor-local.py` réutilise `ml.monitoring.DriftMonitor`, sans
le modifier, pour un bac à sable synthétique borné :

| Mesure | Règle locale | Interprétation |
| --- | --- | --- |
| Observations récentes | moins de 100 : insuffisant | pas de conclusion de stabilité |
| PSI | supérieur à 0,25 | changement de distribution indicatif |
| Taux d'alertes | supérieur à 0,20 | proportion dépassant le seuil synthétique 0,98 |
| KS | restitué, pas d'alerte propre | complément de distribution, pas qualité métier |
| Brier/feedback | absent sans labels | aucune preuve de calibration ni précision |

Référence uniforme synthétique de 1 000 scores ; fenêtre de 1 000. Les scores
sont des rangs non calibrés, pas des probabilités. Les seuils sont pédagogiques,
à valider sur les populations réelles avant toute exploitation. Aucun
réentraînement automatique n'est déclenché.

Canal explicitement nommé **`local-file-test`** : fichiers JSON d'événements
`firing` puis `resolved`, sans destinataire réseau ni acquittement humain.
Restitution textuelle JSON et exposition au format Prometheus `.prom` : lisible
sans couleur, compatible lecteur d'écran, sans identifiants personnels, token
ou payload métier. Les archives se relisent après redémarrage ; elles ne
restaurent pas les compteurs en mémoire du service. Conservation laissée à
l'opérateur dans un dossier local neuf ; aucune collecte de données réelles.

## Reproduction locale isolée et résultats

Depuis la racine du dépôt :

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -o addopts='' \
  tests/test_operations_local.py tests/test_delivery_workflow.py
bash -n deploy/deploy-pilot.sh
git diff --check
OUT="$(mktemp -d /tmp/iddrv-operations.XXXXXX)/sandbox"
PYTHONDONTWRITEBYTECODE=1 python3 deploy/monitor-local.py --output "$OUT"
```

Résultat après correction P1 : **19 tests réussis** (suites operations et
 delivery), syntaxe shell et `git diff --check` valides. Docker est remplacé par
un exécutable factice dans un dossier temporaire : échecs migration, remplacement
runtime puis échec, et épuisement des sondes readiness suivis d'un rollback vers
A avec conservation de B ; succès puis rollback normal ; récupération échouée
puis retentée ; refus sans confirmation schéma, SHA persisté invalide, last-good
absent ou verrou existant. Le faux runtime enregistre le SHA demandé ; le faux
`sleep` supprime uniquement l'attente des tests. Aucun Docker réel n'est exécuté
pour cette correction : ce n'est ni une migration réelle ni une preuve de
disponibilité applicative.

Commande de validation statique reproductible (valeurs exclusivement fictives) :

```sh
POSTGRES_DB=isolated_test POSTGRES_USER=isolated_test \
POSTGRES_PASSWORD=not-a-secret \
OWNER_DATABASE_URL=postgresql://owner:fixture@timescaledb/isolated_test \
API_DATABASE_URL=postgresql://api:fixture@timescaledb/isolated_test \
WORKER_DATABASE_URL=postgresql://worker:fixture@timescaledb/isolated_test \
SESSION_SECRET=local-fixture-not-for-deployment-000000000 \
GHCR_OWNER=local-test IMAGE_TAG=01fcb4fa8daa8261ca34cf2e44171a4d7836af5b \
docker compose --env-file /dev/null -f deploy/compose.pilot.yml config --quiet
```

Compose v2.40.2 a reconnu le manifeste avec `config --quiet` et uniquement des
valeurs fictives passées explicitement, `--env-file /dev/null`, sans contacter
le daemon. Configuration valide, **services non démarrés**.

Exécution réelle du calcul synthétique :
`/tmp/iddrv-operations.rM5f4x/sandbox` (archive locale non versionnée). Deux règles
en firing après décalage injecté puis deux resolved au rétablissement ; JSON
relu dans le test. Cela démontre la collecte/calcul/restitution locale sur
scores synthétiques, pas une alerte reçue en production ni un incident réel.

Restent nécessaires : livraison effective du SHA final en environnement dédié,
preuve migration/rollback avec données sauvegardées, métriques du scorer vivant,
réception par canal opérationnel approuvé, seuils terrain et feedback retardé.
Les anciens audits marqués « acquis » ne sont pas repris comme validations.
