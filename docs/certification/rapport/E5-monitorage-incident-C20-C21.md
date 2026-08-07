# Rapport E5 — Monitorage et résolution d'un incident

**Compétences :** C20 à C21 — **Pages cible :** 2–5 — **Statut :** brouillon rédigé (incident réellement reproduit le 2026-08-07)

---

## 1. Surveillance (C20)

Le pilote expose plusieurs niveaux de surveillance :

- **Healthchecks Docker Compose** sur TimescaleDB et Redis (statut `healthy` vérifié) et healthcheck du worker d'ingestion via heartbeat (`data/processing/.worker_heartbeat`, âge maximum 90 s) ;
- **Endpoint `/health`** de l'API FastAPI et endpoint `/metrics` protégé (token scraper ou session admin) ;
- **Logs structurés** du worker d'ingestion : chaque tentative d'import est tracée, avec fichier, site et résultat ;
- **Statuts d'import persistés** dans `import_jobs` : `discovered`, `retry_wait`, `failed`, `quarantined`, `completed` — avec `attempt_count`, `max_attempts`, `last_error_code` et chemins de fichiers.

Le cycle d'ingestion est `inbox → processing → archive/quarantine`, avec retries
à backoff et **reprise après redémarrage** (le worker récupère les fichiers
restés en `processing`).

## 2. Incident reconstitué (C21)

**Cas :** dépôt d'un fichier industriel corrompu (octets binaires invalides, encodage
UTF-8 cassé) dans l'inbox du site 1. Incident **reconstitué en environnement de
test** le 2026-08-07, résolu et vérifié. Fiche complète :
[`preuves/E5/fiche-incident.md`](./preuves/E5/fiche-incident.md).

### Chronologie

1. **Dépôt** : `export_presse_corrompu_20260807.csv` déposé dans `data/inbox/1/` ; `file` le détecte comme `data` (binaire), pas comme un export texte.
2. **Détection** : le worker découvre le fichier et tente l'import — le profiler ne reconnaît pas un format exploitable.
3. **Impact** : l'import métier est bloqué ; **aucune donnée partielle** — 0 passport, 0 cycle, 0 OF créés (vérifié en base après incident).
4. **Tentatives** : 3 tentatives (`max_attempts=3`) avec backoff, toutes en échec (`last_error_code = import_failed`).
5. **Quarantaine automatique** : le fichier est déplacé vers `data/quarantine/1/export_presse_corrompu_20260807.csv.618343636e0c` ; le job reste tracé avec son hash SHA-256 (`61834363...`).
6. **Diagnostic** : `probe` en lecture seule confirme `INGEST_UNSUPPORTED_FORMAT` — encodage invalide, sans aucune écriture en base.
7. **Vérification finale** : statut `quarantined` dans `import_jobs`, fichier présent en quarantaine, tables métier intactes.

### Fiche d'incident (résumé)

| Champ | Valeur |
|---|---|
| Identifiant | INC-2026-08-07-001 |
| Déclenchement | Dépôt d'un fichier corrompu (UTF-8 invalide) |
| Impact | Import bloqué, données existantes intactes, aucune donnée partielle |
| Cause racine | `INGEST_UNSUPPORTED_FORMAT` — format non reconnaissable |
| Correction | Quarantaine automatique après 3 tentatives ; aucun correctif en base nécessaire |
| Vérification | `probe` lecture seule + comptage base (0 cycle / 0 OF / 0 passport) |
| Prévention | `probe` avant rejeu, mapping versionné, test de non-régression, idempotence SHA-256 + verrou |

## 3. Résolution et reprise

Le chemin de reprise est **non destructif** :

1. **Diagnostiquer** : consulter le job (`import_jobs`) et les logs ; vérifier encodage, délimiteur, colonnes, structure et hash ;
2. **Prouver l'absence de données partielles** : vérifier qu'aucun passport/cycle/OF n'a été créé pour le fichier ;
3. **Corriger** : soit le fichier source (encodage, structure), soit le mapping versionné ;
4. **Rejouer proprement** : lancer `probe` (lecture seule) d'abord, puis redéposer le fichier corrigé dans `inbox/<site>/` ;
5. **Vérifier** : statut final `completed`, absence de doublon grâce au hash SHA-256 et au verrou PostgreSQL (idempotence).

## 4. Tests et prévention

- Tests automatisés de quarantaine, reprise et idempotence (G5 : `tests/test_ingest_g5.py` — 16 checks ingestion) ;
- Mapping versionné (`arburg-selogica-gestica-v1`) et échantillon anonymisé de non-régression ;
- Mode `probe` **read-only** : rapporte parser/mapping/colonnes inconnues/unités/valeurs invalides/confiance sans écrire en base ;
- Heartbeat worker + healthcheck Compose : détection d'un worker mort en ≤ 90 s.

## 5. Conclusion

L'incident a été **contenu automatiquement** : le fichier corrompu n'a jamais
touché les tables métier, sa trace complète est conservée (hash, erreur, chemin),
et la reprise est scriptée et vérifiable. Le comportement est « **prêt pour
pilote** » : la surveillance, la quarantaine et la reprise sont démontrées en
environnement de test ; une validation terrain complète reste à faire avec des
fichiers réels du site.

## 6. Preuves

- [`preuves/E5/fiche-incident.md`](./preuves/E5/fiche-incident.md) — fiche complète avec traces (créée à partir d'une reproduction réelle)
- `ingest/watcher.py` — cycle inbox → processing → archive/quarantine, retries, reprise
- `ingest/profiler.py`, `ingest/loader.py`, `ingest/probe.py` — diagnostic lecture seule
- `data/quarantine/1/export_presse_corrompu_20260807.csv.618343636e0c` — fichier en quarantaine
- `tests/test_ingest_g5.py` — tests de quarantaine, reprise, idempotence
- `docs/on-prem-runbook.md`, `docker-compose.yml` — healthchecks, heartbeat, `/health`
