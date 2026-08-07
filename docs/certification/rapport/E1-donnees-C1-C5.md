# Rapport E1 — Collecte, stockage et mise à disposition des données

**Compétences :** C1 à C5 — **Pages cible :** 2–5 — **Statut :** brouillon rédigé (volumes vérifiés sur les sources 2026-08-07)

---

## 1. Contexte et besoin (C1)

Dans une usine d'injection plastique, l'**ERP** décrit les ordres de fabrication
(OF) et les équipes au niveau macro, tandis que les **presses** produisent un
signal détaillé **par cycle** (temps, pressions, températures, forces, énergie).
Ces deux mondes ne parlent pas le même langage :

- formats **hétérogènes** : exports Arburg (texte), Engel (CSV), fichiers
  transposés (UTF-16), tableurs ERP (XLSX) ;
- **vocabulaires différents** : chaque constructeur nomme ses paramètres à sa
  façon (EUROMAP 77/83 fournit le vocabulaire canonique, pas les exports bruts) ;
- **granularités différentes** : un OF couvre des centaines de cycles.

Le besoin d'IDDRV est de transformer ces exports industriels hétérogènes en
**données fiables, réconciliées et accessibles par API**, sans réécriture
manuelle ni perte d'information.

## 2. Collecte et profilage (C1)

Le pipeline d'ingestion est **déclenché par dossier surveillé** (watched folder) :

```text
inbox → processing → archive / quarantine
```

- `ingest/watcher.py` surveille `data/inbox/<site>/`, détecte les fichiers
  stables (double observation espacée), récupère les fichiers restés en
  `processing` après un redémarrage, applique retries avec backoff et
  **quarantaine automatique** après `max_attempts` échecs ;
- `ingest/profiler.py` détecte **encodage, délimiteur, orientation et marque**
  du fichier avant tout traitement ;
- `ingest/loader.py` lit les formats pris en charge : CSV, texte, UTF-16
  transposé et Excel (XLSX) ;
- **Idempotence** : hash SHA-256 du fichier + verrou PostgreSQL → un fichier
  déjà importé n'est jamais réimporté (aucun doublon, même après rejeu).

Preuve d'exploitation : l'incident reconstitué (fichier corrompu) a montré la
détection, les 3 tentatives, la quarantaine et l'intégrité des données — voir
[rapport E5](./E5-monitorage-incident-C20-C21.md).

## 3. Normalisation (C2)

`ingest/mapper.py` homogénéise les colonnes des fichiers sources vers le
**modèle canonique EUROMAP 77/83** :

- correspondance des noms de colonnes et des unités vers le vocabulaire commun ;
- les **colonnes inconnues sont conservées** (pas de perte d'information) et
  signalées ;
- les **valeurs invalides** sont détectées et rapportées (code, unité, valeur).

Le mapping est **versionné** (`arburg-selogica-gestica-v1` pour les exports
Arburg Selogica/Gestica), ce qui permet de qualifier chaque version de mapping
et de rejouer un import après correction.

## 4. Réconciliation (C3)

`ingest/reconciler.py` rattache les **cycles** aux **OF** et aux **équipes**
avec un **score de confiance** :

- croisement `machine_erp_ref` + fenêtre temporelle + numéro de cycle avec les
  OF de l'ERP ;
- les cycles non rattachés restent tracés (pas de rejet silencieux) ;
- la réconciliation est rejouable et idempotente.

## 5. Stockage (C3)

Deux moteurs complémentaires :

- **PostgreSQL** : référentiel applicatif — sites, lignes, machines, OF,
  équipes, imports (passports), incidents, investigations ;
- **TimescaleDB** : hypertable `machine_cycles` pour les données de série
  temporelle (requêtes temporelles, agrégations par fenêtre).

**Volumes vérifiés sur les sources de démonstration (2026-08-07) :**

| Élément | Valeur vérifiée |
|---|---:|
| Cycles machine (3 machines : 152, 1003, 606) | **38 313** |
| Ordres de fabrication (ERP `erp_orders.xlsx`) | **60** |
| Fichiers sources | 3 CSV cycles + 1 XLSX ERP |

*Les volumes correspondent aux fichiers sources `data/raw/` ; la base locale
est rejouée pour la démonstration orale.*

## 6. API (C5)

FastAPI expose les données normalisées :

- ressources : sites, machines, timelines (cycles), qualité, incidents,
  investigations, imports ;
- **contrats Pydantic** (`docs/api-v1-contract.md`) : schémas d'entrée/sortie
  validés ;
- **requêtes temporelles** (fenêtres, agrégations) ;
- **isolation par site** : un client d'un site ne voit pas les données d'un
  autre site (404 cross-site).

## 7. Données personnelles (C4)

Les données traitées sont des **données de production industrielle**, sans
données personnelles dans le périmètre du pilote. Les mesures appliquées :
minimisation (colonnes du contrat EUROMAP uniquement), pseudonymisation
(identifiants internes), **stockage on-premise** (DB non exposée au LAN),
sécurité (Argon2id, cookie HttpOnly, RBAC, isolation par site), traçabilité
(hash SHA-256, passports d'import) et **aucun export vers le cloud**.

Note complète : [`preuves/E1/note-rgpd.md`](./preuves/E1/note-rgpd.md).
Limite assumée : pas d'AIPD formelle dans le pilote — à compléter avec le
responsable du site avant déploiement.

## 8. Conclusion

IDDRV transforme des exports hétérogènes en **données fiables, réconciliées,
stockées dans un référentiel temps réel et exposées par API**, avec traçabilité
complète et idempotence. Le pipeline est **« prêt pour pilote »** : les
comportements (profilage, quarantaine, reprise, réconciliation) sont
démontrés et testés ; la qualification terrain avec de vrais exports du site
reste à faire.

## 9. Preuves

- `ingest/watcher.py`, `ingest/profiler.py`, `ingest/loader.py`, `ingest/mapper.py`, `ingest/reconciler.py`
- `db/init.sql` — schéma PostgreSQL/TimescaleDB
- `docs/api-v1-contract.md` — contrats API
- `docs/superpowers/specs/industrial-ingestion-backend-db-design.md` — conception
- `data/raw/` — fichiers sources (38 313 cycles, 60 OF)
- [`preuves/E1/note-rgpd.md`](./preuves/E1/note-rgpd.md) — note RGPD (C4)
- `docs/certification/rapport/E5-monitorage-incident-C20-C21.md` — incident reconstitué (preuve du pipeline)
