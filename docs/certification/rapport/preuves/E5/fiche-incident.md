# Fiche d'incident — Fichier industriel corrompu (reconstitué)

| Champ | Valeur |
|---|---|
| Identifiant | INC-2026-08-07-001 |
| Date et environnement | 2026-08-07, ~15:50 (Europe/Paris) — environnement de test local (Docker Compose, TimescaleDB `iddrv`) |
| Statut | Incident reconstitué en environnement de test, résolu et vérifié |
| Déclenchement | Dépôt d'un fichier `export_presse_corrompu_20260807.csv` dans `data/inbox/1/` contenant des octets binaires invalides (UTF-8 corrompu) |
| Impact | Import métier bloqué ; **aucune donnée partielle** (0 passport, 0 cycle, 0 OF créés) ; données existantes intactes |
| Cause racine | Fichier non reconnaissable par le profiler : encodage invalide → `INGEST_UNSUPPORTED_FORMAT` |
| Correction | Aucune correction nécessaire en base : quarantaine automatique après 3 tentatives (`import_failed`) ; le fichier a été déplacé dans `data/quarantine/1/` |
| Vérification | Job `import_jobs` en statut `quarantined` ; `probe` en lecture seule renvoie `INGEST_UNSUPPORTED_FORMAT` ; comptage base : 0 cycle / 0 OF / 0 passport (aucune transaction partielle) |
| Prévention | Mode `probe` (lecture seule) avant tout rejeu ; mapping versionné ; test de non-régression ; hash SHA-256 + verrou PostgreSQL pour l'idempotence |

## Trace de la reproduction

### 1. Dépôt du fichier invalide

```bash
$ mkdir -p data/inbox/1
$ printf 'timestamp;cycle_time_s;pressure_bar\n2026-08-07T10:00:00;42.1;150\n\xff\xfe\x00garbage...\n' \
    > data/inbox/1/export_presse_corrompu_20260807.csv
$ file data/inbox/1/export_presse_corrompu_20260807.csv
data/inbox/1/export_presse_corrompu_20260807.csv: data
```

### 2. Passage du watcher (worker d'ingestion)

```bash
$ python -m ingest.watcher --root data --stable-seconds 2 --poll-seconds 1 --max-attempts 3 --backoff-seconds 2
# 3 tentatives d'ingestion du fichier, toutes échouent
```

### 3. État du job en base

```sql
SELECT id, site_id, source_kind, file_name, status, attempt_count, max_attempts,
       last_error_code, quarantine_path, file_hash
FROM import_jobs;
-- 449557f6-a6a4-40c1-8c3b-c19cce4c4467 | 1 | machine_cycle |
-- export_presse_corrompu_20260807.csv | quarantined | 3 | 3 |
-- import_failed | data/quarantine/1/export_presse_corrompu_20260807.csv.618343636e0c |
-- 618343636e0c313d958d466d6834db5720964bd6f044f0053cb10f92ea725e2e
```

### 4. Vérification par `probe` (lecture seule, sans écriture)

```bash
$ python -m ingest.ingest_pipeline --probe \
    data/quarantine/1/export_presse_corrompu_20260807.csv.618343636e0c \
    --site-id 1 --json
{"error": "INGEST_UNSUPPORTED_FORMAT", "message": "probe_failed"}
```

### 5. Intégrité des données métier après incident

```sql
SELECT status, count(*) FROM import_passports GROUP BY status;  -- (aucune ligne)
SELECT count(*) FROM machine_cycles;                            -- 0
SELECT count(*) FROM production_orders;                         -- 0
```

**Aucune transaction partielle** : le fichier est resté dans le pipeline
`inbox → processing → quarantine` sans jamais atteindre les tables métier.

## Enseignements / prévention

1. **`probe` avant tout rejeu** : vérifier encodage, délimiteur, colonnes, unités et valeurs sans écrire en base.
2. **Quarantaine automatique** : après `max_attempts` échecs, le fichier est déplacé et le job tracé (hash, code d'erreur, chemin).
3. **Idempotence** : le hash SHA-256 et le verrou PostgreSQL empêchent tout double traitement lors d'un rejeu.
4. **Correction possible** : corriger le fichier source (encodage/structure) ou le mapping, puis redéposer dans `inbox/<site>/`.
