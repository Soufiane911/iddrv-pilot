# IDDRV — Architecture d'Ingestion Industrielle & Réconciliation Vault
## Spécification Technique — Plasturgie ERP + Machine

---

## 1. Vision & Objectif

L'**IDDRV (Industrial Data Ingestion & Reconciliation Vault)** est une plateforme d'ingestion hybride qui :
- Accepte des **fichiers batch** (XLSX, CSV, TXT, XML) exportés depuis les ERP et les presses à injecter.
- Supporte un **flux temps réel** via OPC UA / EUROMAP 77.
- Traduit tous les formats propriétaires de constructeurs vers un **modèle canonique unique**.
- Permet à un **agent IA** d'exploiter les données avec une traçabilité totale vers la source brute.

---

## 2. Dictionnaire Canonique Plasturgie (Basé sur EUROMAP 77 / 83)

| Champ Canonique DB | Description | Unité | Code Arburg | Code Engel | Code Haitian |
|---|---|---|---|---|---|
| `cycle_time_s` | Temps de cycle total | s | `t4012` | `t_cycle` | `CycleTime` |
| `dosing_time_s` | Temps de dosage/plastification | s | `t4015` | `t_dos` | `DosingTime` |
| `injection_time_s` | Temps d'injection réel | s | `t4018` | `t_inj` | `InjectionTime` |
| `cushion_mm` | Matelas de matière (pos. vis) | mm/cm³ | `V4062` | `v_mat` | `CushionVolume` |
| `switchover_pressure_bar` | Pression au point de commutation | bar | `p4072` | `p_sw` | `SwitchoverPressure` |
| `switchover_position` | Position vis à commutation | mm/cm³ | `V4065` | `v_sw` | `SwitchoverPos` |
| `peak_pressure_bar` | Pression injection maximale | bar | `p4071` | `p_max` | `PeakPressure` |
| `clamp_force_kn` | Force de verrouillage moule | kN | `f4090` | `f_clamp` | `ClampForce` |
| `mold_open_time_s` | Temps d'ouverture moule | s | `t4030` | `t_mopen` | `MoldOpenTime` |
| `cycle_counter` | Compteur de cycles total | - | `f1403` | `n_cycle` | `CycleCount` |
| `good_parts` | Pièces bonnes dans le cycle | - | `f077` | `n_good` | `GoodParts` |
| `scrap_flag` | Pièce rejetée par la machine | bool | `r_reject` | `q_scrap` | `RejectFlag` |
| `barrel_temp_zone1_c` | Température fourreau zone 1 | °C | `t1001` | `T_z1` | `BarrelTempZ1` |
| `oil_temperature_c` | Température huile hydraulique | °C | `t5001` | `T_oil` | `OilTemp` |

---

## 3. Architecture Générale

```
┌───────────────────────────────────────────────────────────────────┐
│                        SOURCES DE DONNÉES                         │
│  [ERP/TRS XLSX]  [Machine CSV/TXT]  [Transposé UTF-16]  [OPC UA]  │
└────────────┬──────────────┬─────────────────┬──────────┬──────────┘
             │              │                 │          │
             v              v                 v          v
        ┌────────────────────────────────────────────────────────┐
        │              COUCHE D'INGESTION BATCH                   │
        │  ingest/profiler.py  →  ingest/mapper.py  →  ingest/   │
        │  loader.py  →  Raw Store (data/raw/)                    │
        └──────────────────────────┬─────────────────────────────┘
                                   │
                                   v
        ┌──────────────────────────────────────────────────────────┐
        │              MOTEUR DE RÉCONCILIATION                     │
        │  reconcile/temporal_join.py  → Calcul de confiance       │
        │  Jointure Cycle Machine ↔ OF ERP (fenêtre ± 30min)       │
        └──────────────────────────┬───────────────────────────────┘
                                   │
                                   v
        ┌──────────────────────────────────────────────────────────┐
        │           BASE DE DONNÉES HYBRIDE                        │
        │  PostgreSQL (contexte/ERP) + TimescaleDB (cycles/séries) │
        └──────────────────────────────────────────────────────────┘
```

---

## 4. Schéma de Base de Données

### 4.1 Tables Relationnelles (PostgreSQL Classique)

#### `machines`
```sql
CREATE TABLE machines (
    id SERIAL PRIMARY KEY,
    erp_ref VARCHAR(50) UNIQUE NOT NULL,          -- Réf ERP (ex: "1003")
    name VARCHAR(100),                             -- Libellé machine
    brand VARCHAR(50),                             -- Constructeur (arburg, engel...)
    model VARCHAR(100),                            -- Modèle (ex: Allrounder 370C)
    max_clamp_force_kn NUMERIC(8,2),
    max_shot_volume_cm3 NUMERIC(8,2),
    controller_type VARCHAR(50),                   -- Ex: Selogica, Gestica, CC300
    opcua_endpoint VARCHAR(255),                   -- URL serveur OPC UA
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `machine_aliases`
```sql
CREATE TABLE machine_aliases (
    id SERIAL PRIMARY KEY,
    machine_id INT REFERENCES machines(id),
    alias_context VARCHAR(50),     -- 'erp', 'file', 'opcua', 'network'
    alias_value VARCHAR(100),      -- Valeur de l'alias dans ce contexte
    UNIQUE(machine_id, alias_context, alias_value)
);
```

#### `production_orders` (Ordres de Fabrication)
```sql
CREATE TABLE production_orders (
    id VARCHAR(50) PRIMARY KEY,           -- Ex: 'O0824120601331'
    machine_id INT REFERENCES machines(id),
    product_ref VARCHAR(100),
    product_name VARCHAR(255),
    tool_ref VARCHAR(100),                -- Référence du moule
    material_ref VARCHAR(100),
    target_quantity INT,
    operator_id VARCHAR(50),
    shift_id INT,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    erp_cycle_time_s NUMERIC(6,3),        -- Temps de cycle théorique ERP
    erp_trs NUMERIC(5,4),                 -- TRS déclaré par l'ERP
    erp_scrap_count INT DEFAULT 0,
    erp_good_parts INT DEFAULT 0
);
```

#### `shifts` (Équipes)
```sql
CREATE TABLE shifts (
    id SERIAL PRIMARY KEY,
    machine_id INT REFERENCES machines(id),
    shift_number SMALLINT,          -- 1, 2 ou 3
    shift_date DATE NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    operator_id VARCHAR(50),
    planned_duration_h NUMERIC(5,3)
);
```

#### `import_passports` (Traçabilité des Imports)
```sql
CREATE TABLE import_passports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name VARCHAR(255),
    file_hash VARCHAR(64),           -- SHA-256 du fichier source
    file_path_raw TEXT,              -- Chemin vers le brut stocké
    parser_type VARCHAR(50),         -- 'arburg_protocol', 'transposed_utf16', 'erp_xlsx'...
    brand_detected VARCHAR(50),
    encoding_detected VARCHAR(20),
    row_count_total INT,
    row_count_accepted INT,
    row_count_rejected INT,
    column_mapping_confidence NUMERIC(4,3),  -- 0.0 à 1.0
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    error_log TEXT
);
```

#### `evidence_vault` (Preuves pour Agent IA)
```sql
CREATE TABLE evidence_vault (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(20) NOT NULL,       -- 'file' ou 'opcua'
    passport_id UUID REFERENCES import_passports(id),
    file_hash VARCHAR(64),
    sheet_name VARCHAR(100),
    line_start INT,
    line_end INT,
    column_name VARCHAR(100),
    opcua_node_id VARCHAR(255),
    timestamp_start TIMESTAMPTZ,
    timestamp_end TIMESTAMPTZ,
    context_json JSONB                       -- Données contextuelles supplémentaires
);
```

### 4.2 Hypertables TimescaleDB (Séries Temporelles)

#### `machine_cycles` (Hypertable — 1 ligne = 1 cycle injection)
```sql
CREATE TABLE machine_cycles (
    time TIMESTAMPTZ NOT NULL,
    machine_id INT REFERENCES machines(id),
    production_order_id VARCHAR(50),         -- OF réconcilié (peut être NULL)
    passport_id UUID,                        -- Référence import source
    cycle_counter BIGINT,
    cycle_time_s NUMERIC(7,3),
    dosing_time_s NUMERIC(7,3),
    injection_time_s NUMERIC(7,3),
    cushion_mm NUMERIC(6,3),
    switchover_pressure_bar NUMERIC(8,2),
    switchover_position NUMERIC(6,3),
    peak_pressure_bar NUMERIC(8,2),
    clamp_force_kn NUMERIC(8,2),
    mold_open_time_s NUMERIC(7,3),
    good_parts SMALLINT,
    scrap_flag BOOLEAN DEFAULT FALSE,
    barrel_temp_zone1_c NUMERIC(6,2),
    oil_temperature_c NUMERIC(6,2),
    link_confidence NUMERIC(4,3) DEFAULT 1.0,  -- Confiance liaison OF (0.0 à 1.0)
    quality_flag VARCHAR(20) DEFAULT 'valid',   -- 'valid', 'suspect', 'outlier'
    raw_data JSONB                               -- Colonnes supplémentaires brutes
);

-- Conversion en Hypertable TimescaleDB (partitions hebdomadaires)
SELECT create_hypertable('machine_cycles', 'time', chunk_time_interval => INTERVAL '7 days');

-- Politique de compression automatique (données > 30 jours)
ALTER TABLE machine_cycles SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'time',
    timescaledb.compress_segmentby = 'machine_id'
);
SELECT add_compression_policy('machine_cycles', INTERVAL '30 days');
```

#### Vue Continue (Continuous Aggregate) — Synthèse Horaire
```sql
CREATE MATERIALIZED VIEW machine_cycles_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    machine_id,
    production_order_id,
    COUNT(*) AS cycle_count,
    AVG(cycle_time_s) AS avg_cycle_time_s,
    STDDEV(cycle_time_s) AS stddev_cycle_time_s,
    AVG(cushion_mm) AS avg_cushion_mm,
    STDDEV(cushion_mm) AS stddev_cushion_mm,
    AVG(dosing_time_s) AS avg_dosing_time_s,
    SUM(CASE WHEN scrap_flag THEN 1 ELSE 0 END) AS total_scraps,
    COUNT(*) - SUM(CASE WHEN scrap_flag THEN 1 ELSE 0 END) AS total_good,
    AVG(link_confidence) AS avg_link_confidence
FROM machine_cycles
GROUP BY bucket, machine_id, production_order_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('machine_cycles_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 hour');
```

---

## 5. Moteur de Réconciliation Temporelle

### Algorithme de Jointure Floue (Fuzzy Temporal Join)
Pour chaque cycle machine horodaté au temps `T` sur la machine `M` :

1. **Rechercher les OFs actifs** sur la machine M dont la fenêtre `[started_at - 30min, ended_at + 30min]` contient `T`.
2. **Calculer la confiance** :
   - Cycle strictement dans les bornes de l'OF : `link_confidence = 1.0`
   - Cycle en zone de chevauchement (plusieurs OFs) : Confiance proportionnelle à la distance des centres.
   - Cycle sans OF trouvé : `production_order_id = NULL`, `link_confidence = 0.0`
3. **Générer une alerte** si plusieurs OFs se chevauchent (erreur probable de saisie ERP).

---

## 6. Structure des Fichiers du Projet

```
ProjetSeptembre/
├── docker-compose.yml
├── .env.example
├── docs/
│   └── superpowers/
│       └── specs/
│           └── industrial-ingestion-backend-db-design.md  ← CE FICHIER
├── db/
│   ├── init.sql                   ← Initialisation + TimescaleDB
│   └── seed_data.sql              ← Données de référence machines
├── ingest/
│   ├── profiler.py                ← Détection automatique de format
│   ├── mapper.py                  ← Traduction vers modèle canonique
│   ├── loader.py                  ← Insertion en base de données
│   ├── reconciler.py              ← Réconciliation temporelle ERP/cycles
│   └── mappers/                   ← Dictionnaires par constructeur
│       ├── arburg.json
│       ├── engel.json
│       ├── haitian.json
│       └── generic.json
├── data/
│   ├── raw/                       ← Fichiers bruts immuables
│   └── samples/                   ← Données d'exemples générées
└── tests/
    └── test_ingestion.py          ← Tests d'intégration
```
