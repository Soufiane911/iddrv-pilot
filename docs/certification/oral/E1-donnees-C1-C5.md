# Épreuve E1 — Collecte, stockage et mise à disposition des données

**Compétences :** C1 à C5 — **Durée :** 15 minutes  
**Message central :** IDDRV transforme des exports industriels hétérogènes en données fiables, réconciliées et accessibles par API.

## Déroulé conseillé

1. **Problème métier — 1 min 30**
   - L’ERP décrit les OF et équipes au niveau macro ; les presses produisent un signal par cycle.
   - Les formats Arburg, Engel, transposés et ERP sont incompatibles.

2. **Collecte et profilage — 3 min**
   - `ingest/watcher.py` : `inbox → processing → archive/quarantine`.
   - `ingest/profiler.py` détecte encodage, délimiteur, orientation et marque.
   - `ingest/loader.py` lit CSV, texte, UTF-16 transposé et Excel.
   - Hash SHA-256 et verrou PostgreSQL pour l’idempotence.

3. **Nettoyage et réconciliation — 3 min**
   - `ingest/mapper.py` homogénéise les colonnes vers le modèle EUROMAP 77/83.
   - Les colonnes inconnues sont conservées et les valeurs invalides signalées.
   - `ingest/reconciler.py` rattache les cycles aux OF et équipes avec un score de confiance.

4. **Stockage — 3 min**
   - PostgreSQL : sites, lignes, machines, OF, équipes et imports.
   - TimescaleDB : hypertable `machine_cycles`.
   - Démonstration : 60 OF et 38 313 cycles, imports traçables et idempotents.

5. **API — 2 min**
   - FastAPI expose sites, machines, timelines, qualité et incidents.
   - Contrats Pydantic, requêtes temporelles et isolation par site.

6. **Démonstration — 2 min 30**
   - Montrer deux formats source, le profilage, l’import puis une donnée via API/interface.

## Preuves

- `README.md`
- `docs/superpowers/specs/industrial-ingestion-backend-db-design.md`
- `ingest/profiler.py`, `ingest/mapper.py`, `ingest/reconciler.py`
- `db/init.sql`
- `docs/api-v1-contract.md`

## Questions probables

- Comment empêchez-vous les doublons ?
- Comment traitez-vous un fichier corrompu ?
- Pourquoi TimescaleDB ?
- Comment calculez-vous la réconciliation ?
- Quelles mesures RGPD appliquez-vous ?
