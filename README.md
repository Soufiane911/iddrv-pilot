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

Services Docker Compose : `timescaledb`, `redis`, `api` (FastAPI), `worker` (ingestion asynchrone), `web` (nginx → frontend).

## 3. Stack

- **Backend** : Python 3.13, FastAPI
- **Données** : PostgreSQL 16, TimescaleDB, Redis
- **Frontend** : React + Vite + TypeScript
- **ML** : détection de dérive process et risque rebut (modèles `models/*.joblib`)
- **Déploiement** : Docker Compose on-premise + CI/CD GitHub Actions

## 4. Démarrage rapide

Prérequis : Docker + Docker Compose, Python 3.11+.

```bash
git clone https://github.com/Soufiane911/iddrv-pilot.git && cd iddrv-pilot
cp .env.example .env
# Renseigner POSTGRES_PASSWORD dans .env
docker compose up -d --build
```

Charger le scénario industriel de démonstration :

```bash
python db/setup_db.py
python -m ingest.import_scenario data/scenarios/industrial_demo --site-id 1
```

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
| `DOCKER_DATABASE_URL` | requis | URL PostgreSQL utilisée par API/worker dans Compose (`timescaledb` comme hôte) |
| `RAW_STORE_PATH` | `./data/raw` | Répertoire d'archivage des fichiers bruts |
| `POSTGRES_DB` | `iddrv` | Nom de la base (Docker) |
| `POSTGRES_USER` | `iddrv_user` | Utilisateur PostgreSQL (Docker) |
| `POSTGRES_PASSWORD` | requis | Mot de passe PostgreSQL (Docker) |
| `WEB_PORT` | `8080` | Port d'exposition du frontend |

```bash
cp .env.example .env   # puis éditez selon votre environnement
```

## 9. Tests

```bash
python -m pytest -q                        # tests Python
python tests/e2e/run_tests.py --tier 1,2   # tests E2E sur base isolée
npm --prefix frontend run lint             # lint frontend
npm --prefix frontend run test             # tests frontend
npm --prefix frontend run build            # build de production
docker compose config --quiet              # validation Compose
```

La suite d'ingestion couvre notamment : profiling de format (encodage, délimiteur, marque, transposition), mapping de colonnes (Arburg, Engel, générique), chargement des 4 types de fichiers exemples, réconciliation temporelle et validation des données (outliers, timestamps manquants).

## 10. Licence

Projet universitaire — usage pédagogique et de démonstration.
