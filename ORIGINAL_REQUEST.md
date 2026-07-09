# Original User Request

## Initial Request — 2026-07-09T13:14:59Z

Conception et implémentation d'une plateforme d'ingestion de données industrielles unifiée (IDDRV - Industrial Data Ingestion & Reconciliation Vault) pour la plasturgie, réconciliant les données ERP/TRS (macro) et les signaux machine au cycle (micro) via des scripts autonomes Python et une base de données Postgres + TimescaleDB.

Working directory: `/Users/soufianehamzaoui/Desktop/EPSI/ProjetSeptembre`
Integrity mode: development

## Requirements

### R1. Technical Specification Document
Rédiger une spécification d'architecture détaillée sous la forme d'un fichier Markdown `docs/superpowers/specs/industrial-ingestion-backend-db-design.md`. Ce document doit décrire :
* Les schémas de base de données relationnels (contexte usine/ERP) et temporels (cycles machines).
* Le dictionnaire de variables plasturgie basé sur le standard **EUROMAP 77 / 83**.
* La logique de fonctionnement du Profiler de formats et du Moteur de réconciliation temporelle.

### R2. Infrastructure Configuration
Créer un fichier `docker-compose.yml` opérationnel à la racine du projet configurant localement :
* Une base de données PostgreSQL équipée de l'extension TimescaleDB.
* Un serveur Redis servant de tampon de messages pour le streaming temps réel.
* Les variables d'environnement et volumes nécessaires pour la persistance des données.

### R3. Data Models and DB Schema Setup
Créer des scripts d'initialisation SQL et/ou de création de tables Python standalone (en utilisant `psycopg2` or `asyncpg`) pour :
* Configurer la base de données PostgreSQL/TimescaleDB.
* Initialiser les tables de contexte (machines, ordres de fabrication, équipes).
* Configurer l'hypertable `machine_cycles` partitionnée automatiquement par le temps sous TimescaleDB.

### R4. Standalone Ingestion Profiler & Mappers
Développer une suite de scripts Python autonomes (`ingest/`) qui :
* Génèrent des jeux de données d'exemples réalistes (simulation d'exports de machines de plasturgie Arburg et d'autres marques, y compris des fichiers transposés et des fichiers de TRS d'équipes ERP).
* Analysent et profils dynamiquement les fichiers d'entrée (détection de délimiteur, de transposition, d'encodage).
* Mappent et convertissent les données de cycles bruts vers le modèle canonique unifié.
* Insèrent les données normalisées et réconciliées dans la base de données PostgreSQL/TimescaleDB.

## Acceptance Criteria

### Documentation & Infrastructure
- [ ] Le document de spécification `docs/superpowers/specs/industrial-ingestion-backend-db-design.md` est présent et complet.
- [ ] Le fichier `docker-compose.yml` démarre avec succès Postgres (TimescaleDB) et Redis via la commande `docker compose up -d`.

### Database & Ingestion Logic
- [ ] La base de données est initialisée avec l'extension TimescaleDB activée et l'hypertable des cycles machine créée.
- [ ] Le script de profilage redresse correctement les fichiers de cycles simulés (notamment les formats transposés) et les insère dans la table commune de la base de données.
- [ ] Un script de test autonome démontre la réconciliation temporelle réussie entre les données ERP simulées (les OFs) et les cycles machines insérés.
