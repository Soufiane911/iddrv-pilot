# Demande initiale du projet

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

## Follow-up — 2026-07-10T10:18:59Z

Visual redesign of the IDDRV frontend application, upgrading it from a generic light theme to a premium cyber-industrial dark mode dashboard with an interactive, rotating 3D workshop map.

Working directory: `/Users/soufianehamzaoui/Desktop/EPSI/ProjetSeptembre`
Integrity mode: development

## Requirements

### R1. Cyber-Industrial Dark Theme Design System
- Replace the current light-gray theme with a deep blue-black background (`#080b11` or similar).
- Implement translucent glassmorphic card containers (`rgba(17, 24, 39, 0.7)` with `backdrop-filter: blur(12px)` and neon cyan/blue borders).
- Use glowing accent colors for machine status states (Running = pulsing neon green, Warning = amber glow, Stopped = fluorescent red glow).
- Incorporate a modern tech typography layout (e.g. loading Outfit or Space Grotesk from Google Fonts) with monospace tabular numbers for process metrics.

### R2. Interactive 3D Workshop Viewport
- Enable full orbital rotation, panning, and zooming in the Three.js canvas by unlocking `OrbitControls` (`enableRotate={true}`).
- Set a default camera angle showing the workshop in three dimensions rather than flat top-down.
- Enhance the 3D representation of the presses (multi-mesh group showing a machine frame, clamping cylinders, and a glowing neon strip screen matching the machine status).
- Render a neon floor grid (`gridHelper` or shader grid) to ground the elements.
- Enable the 3D mode by default unless explicitly disabled via environment configuration.

### R3. Reference & Ingestion Automation (Completed)
- Automatically load the industrial demo dataset into the dev database during database setup (`setup_db.py`) so the UI immediately shows complete mock data.

## Acceptance Criteria

### Visual & Interactive Quality
- [ ] No generic light panels remain; all pages (Sites, Workshop, Incidents, Imports, Login) follow the dark glassmorphic styling.
- [ ] Workshop 3D view is interactive, allowing rotation/zoom, and shows 3D machine geometries with glowing components.
- [ ] High contrast ratios are maintained for text readability.

### Build & Verification
- [ ] `npm --prefix frontend run lint` passes without warnings.
- [ ] `npm --prefix frontend run test` passes.
- [ ] `npm --prefix frontend run build` compiles the production bundle successfully.
- [ ] Frontend successfully queries and displays the automatically seeded database values.
