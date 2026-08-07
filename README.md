# IDDRV — Industrial Data Ingestion & Reconciliation Vault

> Plateforme d'ingestion de données industrielles unifiée pour la **plasturgie par injection**.
> Réconcilie les données macro ERP/TRS (ordre de fabrication, équipe) avec les signaux machine au cycle (micro) via Python + PostgreSQL/TimescaleDB.

---

## Table des matières

1. [Description du projet](#1-description-du-projet)
2. [Architecture](#2-architecture)
3. [Prérequis](#3-prérequis)
4. [Démarrage rapide](#4-démarrage-rapide)
5. [Formats de fichiers supportés](#5-formats-de-fichiers-supportés)
6. [Modèle canonique EUROMAP 77/83](#6-modèle-canonique-euromap-7783)
7. [Structure du projet](#7-structure-du-projet)
8. [Documentation](#8-documentation)
9. [Variables d'environnement](#9-variables-denvironnement)
10. [Tests](#10-tests)
11. [Contribuer](#11-contribuer)

---

## 1. Description du projet

L'**IDDRV** (Industrial Data Ingestion & Reconciliation Vault) résout un problème concret rencontré dans les usines de plasturgie : les données de production existent à deux grains différents et incompatibles :

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

---

## 2. Architecture

```
╔══════════════════════════════════════════════════════════════════╗
║                    IDDRV — Vue d'ensemble                         ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  Sources externes                                                  ║
║  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            ║
║  │ Arburg       │  │ Engel        │  │ ERP / TRS    │            ║
║  │ .txt (;)     │  │ .csv (,)     │  │ .xlsx        │            ║
║  │ Selogica     │  │ CC300        │  │ Divalto/SAP  │            ║
║  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘            ║
║         │                 │                  │                     ║
║         └────────────┬────┘                  │                     ║
║                       ▼                       ▼                    ║
║  ┌─────────────────────────────────────────────────────────┐      ║
║  │                  ingest/profiler.py                      │      ║
║  │  Détection : encodage, délimiteur, orientation,          │      ║
║  │              marque, ligne d'en-tête                     │      ║
║  └─────────────────────┬───────────────────────────────────┘      ║
║                         ▼                                          ║
║  ┌─────────────────────────────────────────────────────────┐      ║
║  │                  ingest/loader.py                        │      ║
║  │  Chargement + normalisation des valeurs                  │      ║
║  │  (virgule→point, horodatage, hash SHA-256)               │      ║
║  └─────────────────────┬───────────────────────────────────┘      ║
║                         ▼                                          ║
║  ┌─────────────────────────────────────────────────────────┐      ║
║  │                  ingest/mapper.py                        │      ║
║  │  Traduction colonnes propriétaires -> modèle canonique   │      ║
║  │  via mappers/canonical_dict.json (EUROMAP 77/83)         │      ║
║  └─────────────────────┬───────────────────────────────────┘      ║
║                         ▼                                          ║
║  ┌─────────────────────────────────────────────────────────┐      ║
║  │                 ingest/reconciler.py                     │      ║
║  │  Réconciliation temporelle ERP <-> Machine               │      ║
║  │  Algorithme : fenêtre ±30 min, score de confiance        │      ║
║  └─────────────────────┬───────────────────────────────────┘      ║
║                         ▼                                          ║
║  ┌─────────────────────────────────────────────────────────┐      ║
║  │         PostgreSQL 16 + TimescaleDB (Docker)             │      ║
║  │                                                           │      ║
║  │  machines          production_orders    shifts            │      ║
║  │  machine_aliases   import_passports     evidence_vault    │      ║
║  │                                                           │      ║
║  │  * machine_cycles (Hypertable — 1 ligne = 1 cycle)       │      ║
║  │    └─ machine_cycles_hourly (Continuous Aggregate)       │      ║
║  └─────────────────────────────────────────────────────────┘      ║
║                                                                    ║
╚══════════════════════════════════════════════════════════════════╝
```

### Flux de données

```
Fichier machine
     │
     ├─ profiler.py ──> FileProfile (encodage, délimiteur, marque)
     ├─ loader.py ────> List[dict] (lignes normalisées)
     ├─ mapper.py ────> column_map + lignes canoniques
     ├─ ingest_pipeline.py ──> import_passport (traçabilité)
     └─ reconciler.py ─> machine_cycles ──> TimescaleDB
```

---

## 3. Prérequis

| Outil | Version minimale | Rôle |
|-------|-----------------|------|
| **Docker** + Docker Compose | 24.x | Héberge PostgreSQL + TimescaleDB + Redis |
| **Python** | 3.11+ | Scripts d'ingestion |
| **pip** | 23.x | Gestionnaire de paquets Python |

### Paquets Python (`requirements.txt`)

| Paquet | Usage |
|--------|-------|
| `psycopg2-binary` | Connexion PostgreSQL |
| `pandas` | Chargement CSV/XLSX |
| `openpyxl` | Lecture des fichiers Excel `.xlsx` |
| `chardet` | Détection automatique d'encodage |

---

## 4. Démarrage rapide

```bash
# 1. Cloner le dépôt
git clone <url-du-repo> && cd ProjetSeptembre

# 2. Créer un environnement virtuel et installer les dépendances
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# 3. Lancer PostgreSQL + TimescaleDB via Docker
docker compose up -d timescaledb

# 4. Initialiser le schéma (tables, hypertable, index, données de référence)
python db/setup_db.py

# 5. Démonstration end-to-end : génération -> ingestion -> requêtes
python demo_end_to_end.py
```

> **Résultat attendu** : génération de 4 fichiers exemples, ingestion de 3 fichiers machine,
> affichage du résumé (cycles/machine, TRS, anomalies, comparaison ERP vs machine).

---

## 5. Formats de fichiers supportés

### 5.1 Protocole Arburg (`.txt`)

Format propriétaire des presses **Arburg Allrounder** (contrôleurs Selogica / Gestica).

**Caractéristiques :**
- Encodage : UTF-8 ou Latin-1
- Délimiteur : `;` (point-virgule)
- Structure : bloc de métadonnées en en-tête (Machine, Moule, OF, Date...) + tableau de cycles
- Colonnes typiques : `t4012` (cycle), `t4015` (dosage), `V4062` (coussin), `p4072` (pression)

```
Machine;    1003 - 1003 2 NOYAUX
Moule;      M100321
Ordre Fab.; O0824120601331
Date début; 11.02.2025 08:00

t007;t4015;t4012;t4018;V4062;V4065;p4072;p4071;f4090;f077;f1403
h:min;s;s;s;cm3;cm3;bar;bar;kN;-;-
08:00;8.21;28.5;1.85;4.19;52.3;1051;1182;981;1;1
```

### 5.2 Export Engel (`.csv`)

Format d'export des presses **Engel** (contrôleur CC300).

**Caractéristiques :**
- Encodage : UTF-8
- Délimiteur : `,` (virgule)
- Structure : en-tête de colonnes + données (format standard)
- Colonnes typiques : `Timestamp`, `t_cycle`, `t_dos`, `t_inj`, `p_sw`, `f_clamp`

```csv
Timestamp,t_cycle,t_dos,t_inj,v_mat,v_sw,p_sw,p_max,f_clamp,n_good,n_cycle
2025-02-11 14:00:35,35.2,9.1,2.1,6.5,68.0,852,921,2701,1,1
```

### 5.3 Format Transposé UTF-16 (`.txt`)

Format utilisé par certaines machines de type "Tubes" (presses spéciales tuyaux).

**Caractéristiques :**
- Encodage : **UTF-16 LE** (avec BOM)
- Délimiteur : tabulation
- **Orientation transposée** : lignes = paramètres, colonnes = cycles
- Heure stockée en fraction décimale de journée (format tableur)

```
Date          11.02.25  11.02.25  11.02.25
Heure         0,333...  0,334...  0,334...
CycleTime     22,812    22,793    22,834
DosingTime    6,523     6,489     6,511
```

### 5.4 Export ERP/TRS (`.xlsx`)

Export Excel issu des ERP industriels (Divalto, SAP, Sylob, GPAO maison).

**Caractéristiques :**
- Format : Excel `.xlsx` (openpyxl)
- Grain : 1 ligne = 1 Ordre de Fabrication (OF)
- Colonnes : `Réf OF`, `Réf. Machine`, `T.R.S.`, `Cycle Moyen`, `Nb Cycles`, `Total Rebuts`

---

## 6. Modèle canonique EUROMAP 77/83

Tous les fichiers sont traduits vers un modèle de colonnes **standardisé** inspiré des normes EUROMAP 77 (interface machine-MES) et EUROMAP 83 (plasturgie injection).

### Champs canoniques — table `machine_cycles`

| Champ canonique | Type SQL | Unité | Description |
|----------------|----------|-------|-------------|
| `time` | TIMESTAMPTZ | — | Horodatage du cycle (clé temporelle) |
| `cycle_time_s` | NUMERIC(7,3) | s | Temps de cycle total |
| `dosing_time_s` | NUMERIC(7,3) | s | Temps de dosage/plastification |
| `injection_time_s` | NUMERIC(7,3) | s | Temps d'injection |
| `cushion_mm` | NUMERIC(6,3) | mm/cm3 | Volume coussin (matière résiduelle) |
| `switchover_pressure_bar` | NUMERIC(8,2) | bar | Pression de commutation |
| `switchover_position` | NUMERIC(6,3) | mm | Position de commutation |
| `peak_pressure_bar` | NUMERIC(8,2) | bar | Pression de pic (injection) |
| `clamp_force_kn` | NUMERIC(8,2) | kN | Force de fermeture |
| `mold_open_time_s` | NUMERIC(7,3) | s | Temps d'ouverture moule |
| `good_parts` | SMALLINT | pièces | Nombre de bonnes pièces (0 ou 1) |
| `scrap_flag` | BOOLEAN | — | Indicateur de rebut |
| `barrel_temp_zone1_c` | NUMERIC(6,2) | °C | Température fourreau zone 1 |
| `oil_temperature_c` | NUMERIC(6,2) | °C | Température huile hydraulique |
| `link_confidence` | NUMERIC(4,3) | 0–1 | Score de réconciliation ERP |
| `quality_flag` | VARCHAR | — | `valid` / `suspect` / `outlier` / `sensor_error` |
| `raw_data` | JSONB | — | Colonnes non mappées (données brutes) |

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
  5. Si aucun OF -> production_order_id = NULL,
     link_confidence = 0.0
```

---

## 7. Structure du projet

```
ProjetSeptembre/
├── backend/              <- API FastAPI, sécurité et diagnostic
├── frontend/             <- Application React, vues 2D et 3D
├── ingest/               <- Profilage, mapping, ingestion et worker
├── db/                   <- Schéma, migrations et données de référence
├── data/                 <- Échantillons et scénario industriel
├── evals/                <- Évaluation du moteur de diagnostic
├── tests/                <- Tests Python, API et E2E
├── scripts/              <- Administration, sauvegarde et restauration
├── docs/                 <- Documentation technique et universitaire
├── docker-compose.yml    <- Déploiement local on-premise
├── demo_end_to_end.py    <- Démonstration d'ingestion et réconciliation
└── README.md             <- Point d'entrée du projet
```

---

## 8. Documentation

La documentation est indexée dans [`docs/README.md`](docs/README.md).

- `docs/project/` : demande et cadrage initial ;
- `docs/product/` : brief produit, design et preuves frontend ;
- `docs/certification/` : matrice C1-C21, soutenance et références ;
- `docs/superpowers/` : spécifications et plans détaillés ;
- `docs/archive/` : documents historiques qui ne décrivent plus l'état courant.

---

## 9. Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DATABASE_URL` | requis (voir `.env.example`) | URL PostgreSQL locale complète pour les scripts hôte |
| `DOCKER_DATABASE_URL` | requis | URL PostgreSQL utilisée par API/worker dans Compose (`timescaledb` comme hôte) |
| `RAW_STORE_PATH` | `./data/raw` | Répertoire d'archivage des fichiers bruts |
| `POSTGRES_DB` | `iddrv` | Nom de la base (Docker) |
| `POSTGRES_USER` | `iddrv_user` | Utilisateur PostgreSQL (Docker) |
| `POSTGRES_PASSWORD` | requis, sans valeur par défaut | Mot de passe PostgreSQL (Docker) |

```bash
cp .env.example .env
# Éditez .env selon votre environnement.
# Les caractères réservés du mot de passe doivent être encodés dans les URL PostgreSQL.
```

---

## 10. Tests

```bash
cd ingest
python -m pytest ../tests/test_ingestion.py -v
```

Pour la suite E2E destructive, utiliser exclusivement PostgreSQL local `iddrv_test` et Redis local DB 1, puis définir explicitement dans l’environnement local protégé :

```dotenv
E2E_DATABASE_URL=postgresql://<utilisateur>:<mot-de-passe-encodé>@localhost:5432/iddrv_test
E2E_DESTRUCTIVE_CLEANUP_CONFIRMATION=iddrv_test:truncate-and-redis-1:flush
```

Le runner refuse toute autre cible, les paramètres de routage dans les URL et une base dépourvue de sentinelle E2E. Lancer ensuite `python tests/e2e/run_tests.py --tier 1,2`.

La suite d’ingestion couvre notamment :
- Profiling de format (encodage, délimiteur, marque, transposition)
- Mapping de colonnes (Arburg, Engel, générique, confiance)
- Chargement des 4 types de fichiers exemples
- Réconciliation temporelle (fenêtre, score de confiance, ambiguïté)
- Validation des données (outliers, timestamps manquants)

---

## 11. Contribuer

### Ajouter le support d'une nouvelle marque

1. Ajouter les **signatures** dans `ingest/profiler.py`
2. Enrichir le **dictionnaire** `ingest/mappers/canonical_dict.json`
3. Créer un **fichier d'exemple** dans `ingest/generate_samples.py`
4. Ajouter un **test** dans `tests/test_ingestion.py`

### Ajouter un champ canonique

1. Ajouter la colonne dans `db/init.sql` (table `machine_cycles`)
2. Ajouter l'entrée dans `ingest/mappers/canonical_dict.json`
3. Mettre à jour `ingest/reconciler.py` (INSERT statement)

---

*Projet Septembre EPSI — IDDRV v1.0 — Formation Ingénierie des Données Industrielles*
