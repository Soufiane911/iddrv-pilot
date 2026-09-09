# Summary6 — replay synthétique phase 2

## Livré, pas une activation globale

Profil serveur explicite `HDT_RUNTIME_MODE=summary6_replay`. Sans variable, le
profil `historical` reste le défaut de rollback. Aucun déploiement GitHub,
activation globale, migration live, modification des épisodes ou changement
scientifique du moteur. `ml/summary6` reste byte-identique à la phase 1.

Monitoring **et Atelier** passent par `/summary6/current` avant de monter leurs
composants historiques. Dans ce profil, Atelier est volontairement remplacé par
le replay : Direct est indisponible, ni récupération de métriques historiques
ni POST historique. Ce remplacement large est une limite UX assumée de cette
tranche ; pas encore de panneau archives intégré. Les APIs historiques de lecture
et leurs identités restent inchangées. Le localStorage historique n'est ni lu,
ni transformé, ni effacé par le replay. Site choisi explicitement parmi les sites
autorisés de l'API ; aucun fallback site1, aucune correspondance 152→M1.

Le catalogue `/process-drift/candidates` reste **métadonnée scientifique**, pas
une liste d'activation : aucune référence source_only n'est rendue executable.
L'autorité runtime est `/summary6/current`, distincte du catalogue existant.
Aucun EWM/mean n'est activé. Un échec paquet n'active jamais l'historique.

## Paquet privé et lancement reproductible

Lire aussi [summary6-runtime.md](summary6-runtime.md), notamment confirmation
scientifique échouée et limites de certification. Le paquet local durable n'est
pas distribué par Git. Variables **serveur uniquement**, aucune variable VITE :

    export SUMMARY6_PACKAGE_DIR=/Users/soufianehamzaoui/.local/share/iddrv/summary6/6940a3bcd35d0cea0ad4980644168f22b3908fbd71fc5ff038b721bc6cdacff6
    export SUMMARY6_MANIFEST_SHA256=eb29f9b7d0299085be6c6ad38ec98d77649ead10b9b1fe84029880cc2270da84
    # Configurer API_DATABASE_URL, SESSION_SECRET et les comptes autorisés.
    bash scripts/launch_summary6_replay.sh

Le script vérifie le paquet et les données avant uvicorn sur **127.0.0.1:8096**
(`SUMMARY6_PORT` configurable). Pour le frontend, configurer son proxy/API réelle
vers cette API, jamais `VITE_DEMO_MODE=true`. L'auth cookie habituelle est utilisée.
Aucun compte, secret, modèle binaire ou chemin arbitraire n'est accepté en replay.

Environnement local testé : Python3.13.9, sklearn1.7.2, numpy2.2.6, pandas2.3.3,
scipy1.16.3, joblib1.5.2. Le Dockerfile général reste `python:3.13-slim` avec
contraintes numpy/pandas non exactes : **image Docker summary6 NON certifiée**.
Les observations sont copiées dans l'image, pas le paquet privé. Ne pas activer
ce profil Docker avant de construire/vérifier un environnement exact compatible,
monter le paquet privé en lecture seule et vérifier `/current`. Aucun
assouplissement du loader ni promesse qu'un simple mount suffit. Pas de build
Docker Python exact effectué ici ; smoke exécuté avec Anaconda hôte compatible.

## Observations versionnées, préfixe causal

`data/summary6/manifest.json` et six `M{1..3}-R{1..2}-L15.jsonl.gz`, ~244Ko.
Source approuvée et SHA enregistrés dans le manifeste ; SHA du manifeste ancré
dans le service, SHA de chaque gzip vérifié avant décodage. Extraction offline :

    python scripts/extract_summary6_demo.py /chemin/observations.csv.gz

Ce script refuse toute autre source SHA. Sélection déterministe L15, sans
sélection sur résultats. Compteurs originaux0..399, timestamp, huit capteurs,
unités et identités exactes. Aucun outcome/épisode/label/split distribué.
Le runtime lit les octets compressés pour vérifier l'intégrité, mais décode et
transmet au moteur **seulement** les lignes0..cutoff. Ni futur décodé ni fenêtre
renumérotée. Maximum400 résultats, pas d'accès fichier contrôlé par le client.

## Contrat / sécurité

Toutes les routes exigent session réelle, même en développement :

- GET `/api/v1/process-drift/summary6/current` : selected/loaded package IDs,
  readiness, replay_enabled, live_enabled=false, reasons, active_mode.
- GET `.../demo-datasets?site_id=7` : manifeste synthétique autorisé pour ce site.
- POST `.../replay` : JSON strict `{site_id,expected_package_id,source}` ; source
  discriminée uniquement `{kind:"demo_dataset",dataset_id,lot_id,through_cycle}`.
  Aucun chemin, upload, paramètre modèle, conversion implicite ou recalibration.

401 session absente/invalide, 403 site non autorisé (adaptation locale explicite
du require_site historique qui masque en404), 422 contrat/dataset inconnu,
409 profil non activé ou identité obsolète, 503 paquet/données invalides. Les
exceptions loader ne sont jamais exposées. Hash code/environnement/payload
vérifiés avant pickle à chaque requête ; aucun cache ne masque un remplacement.

Réponse : identité effective et pin manifeste, site, mode, provenance synthétique,
contexte/unités, timestamp de coupure, compteur, input_count, latest et série
bornée. Les noms moteur `instant_score`, `decision_score`, `threshold`,
`status=available|abstained`, `reason`, `alert` nullable sont préservés.
Abstention200 ne signifie jamais `alert:false`. `signals=[]`, aucun faux horizon
qualité. Pas de DB write, job, incident, correction ni métrique historique.

Métriques Prometheus dédiées `iddrv_summary6_replay_*` : résultats/raisons à
cardinalité bornée, latence, score brut/min3, alertes synthétiques. Elles comptent
les requêtes effectivement calculées (un recalcul manuel compte de nouveau),
pas des incidents ni des prédictions live ; aucune PSI calibrée, aucun feedback
historique. Erreurs transport restent dans la famille HTTP générale.

## Bascule et rollback opérateur

1. Vérifier le smoke ci-dessous et `/current` avec le paquet privé approuvé.
2. Arrêter proprement les workers historiques existants, attendre la fin des
   transactions en cours ; ne pas changer seulement TELEMETRY_MODEL_VERSION.
3. Redémarrer API ET collecteurs/workers avec HDT_RUNTIME_MODE=summary6_replay.
   Le collecteur conserve les observations mais n'enfile aucun scoring job ;
   claim/score/finish/recalculation historiques sont suspendus explicitement.
   Ne pas interpréter le heartbeat worker comme un live summary6 connecté.
4. Vérifier POST historique409 et Direct absent ; jobs/épisodes anciens intacts.
5. Rollback explicite : arrêt contrôlé, HDT_RUNTIME_MODE=historical, redémarrage
   cohérent de tous les processus. Les identités des jobs en file sont conservées.
   Les observations collectées pendant suspension n'ont pas de jobs ; aucun
   backfill automatique n'est fabriqué au rollback.

Changer uniquement l'environnement API ne peut pas arrêter un ancien worker
déjà lancé avec un autre environnement. Le script de lancement ne gère pas la
stack utilisateur ; cette coordination reste une responsabilité opérateur.

## Vérifications réellement exécutées

Commande Python avec SUMMARY6_TEST_PACKAGE et SUMMARY6_TEST_MANIFEST_SHA256
pointant sur le paquet privé approuvé :

    python -m pytest -q tests/test_summary6_api.py tests/test_summary6_runtime.py tests/test_summary6_package.py tests/test_process_drift_api.py tests/test_telemetry_collector.py tests/test_telemetry_contract.py tests/test_telemetry_http.py

**83 passed, 13 skipped** (tests collecteur DB existants non activés). Contrats,
auth/signatures (repository sessions stub dans TestClient), isolation, identité409,
hash invalide avant joblib503, cutoff59/79/83/84/399, causalité de série et six
contextes, absence de champs interdits, garde worker/POST et rollback historique.

    cd frontend
    npx vitest run src/test/summary6Replay.test.tsx src/test/processDrift.test.tsx src/test/workshopLive.test.tsx
    npx tsc --noEmit
    npx tsc -b

**14 tests passed**, typecheck OK. Mode/erreur fail-closed, abstention, identité,
cutoff effaçant résultat, aucune invocation historique, rollback. Dépendances
réutilisées via symlink temporaire, retiré après vérification.

### Smoke HTTP réel distinct de TestClient

    # Les deux variables privées de lancement ci-dessus doivent être définies.
    python scripts/smoke_summary6_local.py

**PASS effectivement exécuté** : Docker local image déjà présente
`timescale/timescaledb:2.28.2-pg16`, conteneur nommé UUID, stockage tmpfs,
port Postgres loopback aléatoire ; init SQL + migrations001..022 ; vrai site,
vrai utilisateur/hash, login HTTP, session DB vérifiée, uvicorn loopback avec
paquet réel. Redis n'est pas requis ici : test auth avec limiteur mémoire local,
URL Redis loopback port0 (aucune stack existante contactée).

Résultats min3 :59=null,79=null,83=0.42204178647765367 (abstention),
84=0.4179955185182244 (available),399=0.455445834063937 (available).
401 sans session,403 autre site, compte incidents inchangé. Processus API arrêté
et **seul** conteneur UUID créé supprimé en finally. Aucun tests/e2e destructif
sur stack inconnue, aucun volume utilisateur, aucun push/merge.

Ce smoke n'est **pas** une certification navigateur Playwright, ni un test de
migration live/collecteur, ni une confirmation scientifique multi-lots complète.
Pas d'activation globale exécutée. Test navigateur visuel complet, image Docker
exacte, UI archives dédiée, persistance live/contextes autorisés restent à faire.
