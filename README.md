# IDDRV — Industrial Data Ingestion & Reconciliation Vault

Plateforme on-premise de supervision et d'investigation industrielle pour la plasturgie par injection.

Elle réconcilie les données des ERP/TRS (ordres de fabrication, équipes, rebuts) avec les signaux machine au cycle (presses d'injection) pour détecter les incidents et aider à la décision.

Projet réalisé par **Soufiane Hamzaoui** dans le cadre de la certification **DEVIA (RNCP 37827)** à l'**EPSI**.

---

## 1. Description du projet

Les données de production existent à deux grains différents et incompatibles :

| Grain | Source | Exemple |
|-------|--------|---------|
| **Macro** | ERP (SAP, Divalto, Sylob…) | TRS horaire, quantité d'OF, rebuts par équipe |
| **Micro** | Machines (Arburg, Engel, KM…) | 1 ligne = 1 cycle d'injection (~15 à 60 s) |

Le pipeline IDDRV :

- **Profile** automatiquement les fichiers d'export machine (encodage, délimiteur, format transposé…)
- **Mappe** les colonnes propriétaires vers un modèle canonique EUROMAP 77/83
- **Réconcilie** temporellement chaque cycle avec l'OF ERP correspondant
- **Charge** les données dans une hypertable TimescaleDB pour l'analyse temps-réel
- **Trace** chaque import avec un passeport (hash, confiance, anomalies)
- **Supervise** en continu : monitoring, détection de dérive process et estimation du risque rebut

## 2. Architecture

```
Sources externes
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Arburg .txt  │  │ Engel .csv   │  │ ERP/TRS.xlsx │
│ (Selogica)   │  │ (CC300)      │  │ Divalto/SAP  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       └─────────────────┴─────────────────┘
                         ▼
        ingest/ (profiler → loader → mapper → reconciler)
                         ▼
        PostgreSQL 16 + TimescaleDB (Docker)
        ├─ machine_cycles (hypertable, 1 ligne = 1 cycle)
        ├─ machine_cycles_hourly (continuous aggregate)
        └─ production_orders, shifts, import_passports, evidence_vault
                         ▼
        backend/ FastAPI (API v1, diagnostic, monitoring)
                         ▼
        frontend/ React + Vite + TypeScript (vues 2D/3D, admin, monitoring)
```

Services Docker Compose : `timescaledb`, `redis`, `migrate` (owner/schema), `api` (FastAPI), `worker` (ingestion asynchrone), `web` (nginx → frontend).

## 3. Stack

- **Backend** : Python 3.13.x, FastAPI
- **Données** : PostgreSQL 16, TimescaleDB, Redis
- **Frontend** : React + Vite + TypeScript
- **ML** : détection de dérive process et risque rebut (modèles `models/*.joblib`)
- **Déploiement** : Docker Compose on-premise + CI/CD GitHub Actions

## 4. Démarrage rapide

Prérequis : Docker + Docker Compose et **Python 3.13.x** (la version utilisée pour
les modèles publiés). Les commandes Python ci-dessous supposent un environnement
virtuel depuis la racine du dépôt.

```bash
git clone https://github.com/Soufiane911/iddrv-pilot.git && cd iddrv-pilot
cp .env.example .env
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Éditer `.env` avant de démarrer : renseigner `POSTGRES_PASSWORD`,
`OWNER_DATABASE_URL` et `DOCKER_DATABASE_URL` pour le compte owner, ainsi que
`API_DATABASE_URL` et `WORKER_DATABASE_URL` pour les deux comptes runtime
séparés (mots de passe URL-encodés), et un `SESSION_SECRET` aléatoire d'au
moins 32 caractères. En mode pilot, les deux URLs runtime sont obligatoires.
Puis charger
les variables pour les commandes lancées sur l'hôte :

```bash
set -a; . ./.env; set +a
docker compose up -d --build
```

Le service `migrate` applique le schéma et les grants au démarrage ; l'API et
le worker n'exécutent pas de DDL. Pour charger le scénario industriel de
démonstration, utiliser le wrapper documenté (il ne lit
jamais `ground_truth.json`) :

```bash
.venv/bin/python -m ingest.import_scenario \
  data/scenarios/industrial_demo --site-id 1
```

L'ancien point d'entrée reste compatible :
`python -m ingest.ingest_pipeline --scenario <répertoire> <site_id>`.
Accès à l'interface : http://localhost:8080

## 5. Formats de fichiers supportés

### 5.1 Protocole Arburg (`.txt`)

Presses **Arburg Allrounder** (contrôleurs Selogica / Gestica). Encodage UTF-8 ou Latin-1, délimiteur `;`, bloc de métadonnées en en-tête (Machine, Moule, OF, Date) puis tableau de cycles.

```
Machine;    1003 - 1003 2 NOYAUX
Moule;      M100321
Ordre Fab.; O0824120601331
Date début; 11.02.2025 08:00

t007;t4015;t4012;t4018;V4062;V4065;p4072;p4071;f4090;f077;f1403
08:00;8.21;28.5;1.85;4.19;52.3;1051;1182;981;1;1
```

### 5.2 Export Engel (`.csv`)

Presses **Engel** (contrôleur CC300). Encodage UTF-8, délimiteur `,`, en-tête de colonnes puis données.

```csv
Timestamp,t_cycle,t_dos,t_inj,v_mat,v_sw,p_sw,p_max,f_clamp,n_good,n_cycle
2025-02-11 14:00:35,35.2,9.1,2.1,6.5,68.0,852,921,2701,1,1
```

### 5.3 Format transposé UTF-16 (`.txt`)

Presses spéciales type "Tubes". Encodage **UTF-16 LE** (BOM), délimiteur tabulation, **orientation transposée** (lignes = paramètres, colonnes = cycles), heure en fraction décimale de journée.

```
Date          11.02.25  11.02.25  11.02.25
Heure         0,333...  0,334...  0,334...
CycleTime     22,812    22,793    22,834
DosingTime    6,523     6,489     6,511
```

### 5.4 Export ERP/TRS (`.xlsx`)

Export Excel issu des ERP (Divalto, SAP, Sylob, GPAO maison). Grain : 1 ligne = 1 Ordre de Fabrication. Colonnes : `Réf OF`, `Réf. Machine`, `T.R.S.`, `Cycle Moyen`, `Nb Cycles`, `Total Rebuts`.

## 6. Modèle canonique EUROMAP 77/83

Tous les fichiers sont traduits vers un modèle de colonnes **standardisé** inspiré des normes EUROMAP 77 (interface machine-MES) et EUROMAP 83 (plasturgie injection).

Champs principaux de la table `machine_cycles` : `time` (TIMESTAMPTZ), `cycle_time_s`, `dosing_time_s`, `injection_time_s`, `cushion_mm`, `switchover_pressure_bar`, `peak_pressure_bar`, `clamp_force_kn`, `mold_open_time_s`, `good_parts`, `scrap_flag`, `barrel_temp_zone1_c`, `oil_temperature_c`, `link_confidence` (0–1), `quality_flag` (`valid`/`suspect`/`outlier`/`sensor_error`), `raw_data` (JSONB).

### Algorithme de réconciliation temporelle

```
Pour chaque cycle machine horodaté :
  1. Rechercher les OFs ERP actifs sur la même machine
     dans une fenêtre ±30 min autour du cycle
  2. Si 1 OF strictement -> link_confidence = 1.0
  3. Si plusieurs OFs chevauchants -> prendre le plus récent,
     link_confidence = 0.6
  4. Si aucun OF strict mais candidats dans la fenêtre ->
     link_confidence = 1.0 - (distance_s / 1800)
  5. Si aucun OF -> production_order_id = NULL, link_confidence = 0.0
```

## 7. Structure du projet

```
iddrv-pilot/
├── backend/            <- API FastAPI, diagnostic, monitoring
├── frontend/           <- Application React (vues 2D/3D, admin, monitoring)
├── ingest/             <- Profilage, mapping, réconciliation, worker
├── db/                 <- Schéma, migrations, données de référence
├── ml/                 <- Détection de dérive process, risque rebut
├── models/             <- Modèles entraînés (*.joblib)
├── data/               <- Échantillons et scénario industriel
├── tests/              <- Tests Python, API et E2E
├── docker-compose.yml  <- Déploiement on-premise
└── README.md           <- Point d'entrée du projet
```

## 8. Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DATABASE_URL` | requis (voir `.env.example`) | URL PostgreSQL locale pour les scripts hôte |
| `DOCKER_DATABASE_URL` | requis | URL owner de secours pour Compose/dev (`timescaledb` comme hôte) |
| `OWNER_DATABASE_URL` | requis en pilot | URL du compte owner utilisée seulement par `migrate` |
| `API_DATABASE_URL` | requis en pilot | URL du compte runtime API, sans privilèges DDL |
| `WORKER_DATABASE_URL` | requis en pilot | URL du compte runtime worker, sans privilèges DDL et sans accès auth |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis pour readiness et throttling du login |
| `TRUSTED_PROXY_IPS` | `172.30.0.10/32` (Compose local) | Adresses des proxies contrôlés autorisés à fournir `X-Forwarded-For`/`X-Real-IP`; le manifeste pilot utilise `172.31.0.10/32` |

`API_DATABASE_URL` et `WORKER_DATABASE_URL` doivent cibler la même base avec
des comptes distincts. `db/runtime_roles.py` n'accorde à l'API que les tables
nécessaires à l'authentification, à la lecture et au contrôle ; le worker reçoit
les écritures d'ingestion explicites, sans tables d'authentification. Aucun des
deux rôles n'a accès à `schema_migrations`, aux futures tables par défaut ou au
DDL. Toute nouvelle table utilisée par un runtime doit être ajoutée à la
matrice puis le script de grants doit être rejoué avec le compte owner.

Le throttling du login conserve dans Redis deux compteurs par fenêtre de cinq
minutes : cinq échecs pour un couple identité/origine et vingt échecs pour une
origine. Une authentification valide efface uniquement le compteur du couple,
jamais le quota partagé de l'origine. Nginx réécrit les en-têtes d'adresse avant
le relais ; les en-têtes envoyés directement à l'API sont ignorés.
| `RAW_STORE_PATH` | `./data/raw` | Répertoire d'archivage des fichiers bruts |
| `POSTGRES_DB` | `iddrv` | Nom de la base (Docker) |
| `POSTGRES_USER` | `iddrv_user` | Utilisateur PostgreSQL (Docker) |
| `POSTGRES_PASSWORD` | requis | Mot de passe PostgreSQL (Docker) |
| `WEB_PORT` | `8080` | Port d'exposition du frontend |
| `SESSION_SECRET` | requis en pilot | Secret de signature des sessions (>= 32 caractères) |
| `SESSION_COOKIE_SECURE` | `false` | À activer derrière HTTPS |
| `APP_ENV` | `pilot` | Profil d'exécution (`dev` ou `pilot`) |
| `PROCESS_DRIFT_MODEL_PATH` | `models/process_drift_hdt_v1.joblib` | Artefact HDT chargé par l'API |
| `SCRAP_RISK_MODEL_PATH` | `models/rebut_risk_v1.joblib` | Artefact rebut-risk chargé par l'API |

```bash
cp .env.example .env   # puis éditez selon votre environnement
```

## 9. Limites connues du pilote

- La validation d'une session dans le workspace conserve les métadonnées, mais
  ne raccorde pas encore la session à l'ingestion des fichiers vers
  `machine_cycles`.
- L'état du moniteur HDT (scores et calibration) est en mémoire et est perdu au
  redémarrage ; le feedback d'incident est toutefois conservé dans la base.
- La livraison SSH est inactive par défaut : sans `DEPLOY_ENABLED=true`, le
  workflow signale explicitement « non déployé ». Avec l'environnement pilot,
  un hôte, une clé et un `known_hosts` configurés, il exécute un déploiement
  vérifié sur le SHA validé par CI ; l'infrastructure et les secrets restent
  hors de ce dépôt.
- La pagination v1 conserve temporairement des curseurs base64 d'offset pour
  compatibilité. Les tris ont un départage unique, mais une insertion entre
  deux pages peut encore déplacer l'offset : le client doit relancer la
  lecture depuis la première page dans ce cas.
- Les modèles sont des prototypes évalués sur des données synthétiques. Ne pas
  utiliser `ground_truth.json` pour l'entraînement ou l'ingestion.

## 10. Tests et reproductibilité ML

```bash
.venv/bin/python -m pytest -q --ignore=tests/e2e  # tests produit (non destructifs)
.venv/bin/python scripts/train_process_drift.py --help
.venv/bin/python scripts/train_rebut_risk.py --help
npm --prefix frontend run lint                 # lint frontend
npm --prefix frontend run test                 # tests frontend
npm --prefix frontend run build                # build de production
npm --prefix frontend run test:e2e -- --project=chromium  # smoke UI déterministe
docker compose config --quiet                  # validation Compose
```

La commande pytest produit ignore explicitement `tests/e2e` : les tests E2E
préparés sont destructifs et exigent une base PostgreSQL dédiée `iddrv_test`,
Redis DB 1 et la confirmation de nettoyage documentée. Après avoir préparé
cette infrastructure locale (ou les services CI), remplacer `CHANGE_ME` par le
mot de passe du compte dédié puis lancer séparément :

```bash
E2E_DATABASE_URL=postgresql://iddrv_user:CHANGE_ME@localhost:5432/iddrv_test \
E2E_REDIS_URL=redis://localhost:6379/1 \
E2E_DESTRUCTIVE_CLEANUP_CONFIRMATION=iddrv_test:truncate-and-redis-1:flush \
.venv/bin/python tests/e2e/run_tests.py --tier 1,2
```

Ne pas lancer cette commande contre une base ou un Redis de développement : le
harness initialise puis nettoie la cible dédiée.

Les modèles publiés ont été entraînés avec Python 3.13.9, scikit-learn 1.7.2
et joblib 1.5.2. Les scripts refusent d'écraser un artefact existant sans
`--force`; pour vérifier une régénération, utiliser des chemins de sortie dans
un répertoire temporaire. Les metadata JSON décrivent le contrat de features,
les bornes temporelles, l'environnement et les métriques.

La suite d'ingestion couvre notamment : profiling de format (encodage, délimiteur, marque, transposition), mapping de colonnes (Arburg, Engel, générique), chargement des 4 types de fichiers exemples, réconciliation temporelle et validation des données (outliers, timestamps manquants). Le smoke Playwright Chromium utilise explicitement le client de démonstration (`VITE_DEMO_MODE=true`) : il vérifie l’UI et les parcours, pas l’authentification ni la disponibilité du backend.

## 11. Licence

Projet universitaire — usage pédagogique et de démonstration.
