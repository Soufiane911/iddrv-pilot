# Audit architecture ingestion IDDRV

Date d'audit : 2026-07-09

Objectif : identifier les points faibles avant correction et definir une architecture cible robuste pour l'ingestion de donnees industrielles plasturgie ERP/TRS + cycles machine.

## Synthese

Le projet contient une bonne base de prototype : documentation, schema TimescaleDB, generateur de donnees, profiler, mapper, loader, reconciler et tests unitaires simples. Mais l'architecture actuelle n'est pas encore fiable pour une ingestion industrielle bout en bout.

Les risques principaux sont :

- La base TimescaleDB locale ne demarre pas correctement dans l'etat actuel.
- L'import ERP existe comme fonction, mais n'est pas integre au pipeline principal.
- Les timestamps machine ne sont pas traites de facon fiable pour toutes les marques.
- L'idempotence par cycle n'est pas garantie.
- La couche de staging, validation, rejet et observabilite est insuffisante.
- Les tests E2E visent une plateforme plus ambitieuse que le code actuel.

## Sources externes de reference

- EUROMAP 77 : interface entre machines d'injection et MES pour l'echange de donnees, avec compatibilite multi-constructeurs.
  https://www.euromap.org/euromap77
- EUROMAP OPC UA overview : EUROMAP 83 fournit les types communs, EUROMAP 77 couvre IMM vers MES.
  https://www.euromap.org/i40/OPCUA
- OPC UA Foundation : OPC UA apporte information modeling, acces aux donnees courantes et historiques, notification, securite, signature, chiffrement, authentification et audit.
  https://opcfoundation.org/about/opc-technologies/opc-ua/
- OPC UA / ISA-95 common object model : ISA-95 separe les niveaux atelier, MOM/MES et ERP, avec echanges materiel, equipement, actifs physiques et personnel.
  https://reference.opcfoundation.org/specs/OPC-10030/4
- PostgreSQL COPY : mecanisme standard pour chargement massif, avec options d'encodage, erreurs, colonnes et progression.
  https://www.postgresql.org/docs/current/sql-copy.html
- Timescale / TigerData : hypertables, compression, segmentby/orderby et continuous aggregates doivent etre regles selon les requetes et le cycle de vie des donnees.
  https://docs.tigerdata.com/
- NIST ICS data integrity : les environnements industriels doivent traiter integrite des fichiers, controle des changements, moindre privilege, detection d'anomalies et monitoring.
  https://csrc.nist.gov/pubs/pd/2019/06/12/detecting-and-protecting-against-data-integrity-at/ipd
- OWASP Logging Cheat Sheet : les logs applicatifs doivent etre coherents, exploitables et correlables pour les usages operationnels et securite.
  https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

## Etat local verifie

Commandes verifiees :

```bash
python tests/test_ingestion.py
python tests/e2e/run_tests.py --tier 1 --fail-fast
docker compose ps
docker compose logs --tail=60 timescaledb
```

Resultats :

- `tests/test_ingestion.py` passe : 32 tests reussis, 0 echec.
- `tests/e2e/run_tests.py --tier 1 --fail-fast` echoue au premier test parce que PostgreSQL/TimescaleDB est inaccessible.
- Redis est accessible.
- TimescaleDB redemarre en boucle.
- Le dossier n'est pas un depot Git initialise.

## Points faibles critiques

### 1. Base de donnees non disponible

Impact : aucun test E2E DB, aucune ingestion reelle, aucune reconciliation ne peut etre prouvee.

Preuves locales :

- `docker compose ps` montre `iddrv-timescaledb` en redemarrage.
- `docker compose logs timescaledb` indique que la base est non initialisee et que le mot de passe superuser n'est pas vu par le conteneur actif.
- `docker-compose.yml` contient pourtant `POSTGRES_PASSWORD` a la ligne 12, donc le conteneur courant semble etre dans un etat divergent ou ancien.

Correction cible :

- Repartir d'un conteneur coherent avec le compose actuel.
- Eviter les `container_name` fixes si les tests doivent pouvoir creer des environnements isoles.
- Aligner les credentials de `docker-compose.yml`, `.env.example`, `db/setup_db.py`, `tests/e2e/run_tests.py`.

### 2. Import ERP non integre

Impact : `production_orders` et `shifts` ne sont pas alimentes par le pipeline principal. La reconciliation ERP vers cycles machine est donc surtout theorique.

Preuves locales :

- `ingest/loader.py` expose `read_erp_trs_xlsx(...)`.
- `ingest/ingest_pipeline.py` expose seulement `ingest_machine_file(file_path, machine_erp_ref)`.
- Le pipeline machine appelle `insert_cycles(...)`, mais aucun import ERP equivalent n'insere les OF avant reconciliation.

Correction cible :

- Ajouter un pipeline ERP separe : `ingest_erp_file(...)`.
- Inserer ou mettre a jour `production_orders` et `shifts`.
- Executer la reconciliation apres l'import ERP et machine, pas pendant le parsing.

### 3. Timestamps machine non fiables

Impact : un cycle sans timestamp est rejete ; un cycle avec date fausse est mal reconcilie.

Preuves locales :

- Pour les CSV generiques, `loader.py` force `canonical["time"] = None`.
- Engel contient une colonne `Timestamp`, mais elle part dans `raw_data`.
- Arburg reconstruit la date depuis l'annee seulement et force `YYYY-01-01`, alors que les metadonnees contiennent jour/mois/annee.

Correction cible :

- Centraliser un `TimestampNormalizer`.
- Supporter ISO timestamp, date + heure, heure seule + date de fichier, fraction de jour Excel, timezone explicite ou timezone usine par defaut.
- Rejeter clairement les lignes ambigues avec raison de rejet.

### 4. Idempotence cycle insuffisante

Impact : reimport ou import partiel peut creer des doublons ou masquer des erreurs.

Preuves locales :

- `reconciler.py` utilise `ON CONFLICT DO NOTHING`.
- `db/init.sql` ne definit pas de contrainte unique sur `machine_cycles`.
- `import_passports.file_hash` est indexe mais pas unique.

Correction cible :

- Ajouter `row_hash` calcule depuis source normalisee.
- Ajouter une contrainte unique, par exemple `(machine_id, time, cycle_counter, source_row_hash)` ou `(passport_id, source_line_no)`.
- Distinguer fichier deja importe, ligne deja importee et conflit metier.

### 5. Pas de staging SQL

Impact : impossible de tracer proprement chaque ligne, de rejouer une validation ou de corriger un mapping sans relire le fichier brut.

Correction cible :

```text
raw file
  -> import_passports
  -> staging_import_rows
  -> staging_machine_cycles / staging_erp_orders
  -> validation_results
  -> canonical tables
```

Tables recommandees :

- `staging_import_rows`
- `staging_machine_cycles`
- `staging_erp_orders`
- `import_rejections`
- `mapping_profiles`

### 6. Validation de donnees trop faible

Impact : des donnees incoherentes peuvent etre acceptees, et des donnees valides peuvent etre rejetees sans diagnostic suffisant.

Faiblesses observees :

- Outlier seulement sur `cycle_time_s`.
- Pas de seuil par machine, moule, produit ou programme.
- Pas de verification unite/source.
- Pas de verification de continuite cycle counter.
- Pas de detection de trous temporels, doublons timestamp, inversion de temps, passage minuit.

Correction cible :

- Regles globales : timestamp obligatoire, machine resolue, unite connue, champ obligatoire present.
- Regles process : seuils par machine ou famille de moule.
- Regles serie temporelle : doublons, trous, ordre, compteur.
- Sortie explicite : accepted / warning / rejected.

### 7. Mapping canonique trop pauvre

Impact : le projet dit EUROMAP 77/83, mais le dictionnaire local ne couvre qu'un sous-ensemble minimal.

Faiblesses :

- 9 metriques canoniques seulement.
- Pas de notion de namespace OPC UA / EUROMAP.
- Pas de version de dictionnaire.
- Pas de champs obligatoires par type de fichier.
- Pas de conversion unite explicite documentee.

Correction cible :

- Versionner `canonical_dict.json`.
- Ajouter `source_standard`, `namespace`, `node_id` si applicable, `canonical_unit`, `conversion`.
- Separer les mappings constructeur des metriques canoniques.

### 8. Chargement ligne par ligne

Impact : performance fragile sur gros fichiers.

Reference : PostgreSQL recommande `COPY` pour le chargement massif.

Correction cible :

- Parser vers buffer structure.
- Charger en staging avec `COPY FROM STDIN`.
- Valider et merger vers tables canoniques en SQL transactionnel.

### 9. Observabilite insuffisante

Impact : difficile d'expliquer pourquoi un import a echoue ou pourquoi un cycle n'est pas reconcilie.

Faiblesses :

- `print` au lieu de logs structures.
- Pas de correlation `import_id` dans tous les logs.
- Pas de duree par etape.
- Pas de compteurs normalises.

Correction cible :

- Logs JSON ou logs structures.
- Champs obligatoires : `import_id`, `file_hash`, `machine_id`, `step`, `accepted`, `rejected`, `duration_ms`, `error_code`.
- Table `import_events` ou enrichissement `import_passports.metadata`.

### 10. Tests E2E non alignes avec le code

Impact : les E2E actuels sont utiles comme cible, mais pas comme preuve de l'etat actuel.

Preuves locales :

- Les rapports E2E attendent schema init, profiler, mapper CLI, loader DB, reconciliation.
- Le code actuel valide seulement les tests unitaires simples.
- Le premier E2E echoue sur DB indisponible.

Correction cible :

- Faire une premiere tranche E2E realiste : DB up, schema, import ERP, import Arburg, import Engel, reconciliation, idempotence.
- Ensuite seulement elargir aux cas Tier 2 : gros volume, retry, Redis, conflit, outliers.

## Architecture cible recommandee

```text
                 +---------------------+
                 |  Sources externes   |
                 | ERP XLSX / CSV /    |
                 | Arburg / Engel /    |
                 | Transpose / OPC UA  |
                 +----------+----------+
                            |
                            v
                 +---------------------+
                 | Import Passport     |
                 | hash, source, owner |
                 | config, version     |
                 +----------+----------+
                            |
                            v
                 +---------------------+
                 | Raw Store           |
                 | fichier immutable   |
                 +----------+----------+
                            |
                            v
                 +---------------------+
                 | Profiler            |
                 | encoding, delimiter |
                 | schema, orientation |
                 +----------+----------+
                            |
                            v
          +-----------------+------------------+
          |                                    |
          v                                    v
+---------------------+             +---------------------+
| Staging ERP         |             | Staging Machine     |
| orders, shifts      |             | cycle rows raw/norm |
+----------+----------+             +----------+----------+
           |                                   |
           v                                   v
+---------------------+             +---------------------+
| Validation ERP      |             | Validation Machine  |
| machines, OF, dates |             | time, units, ranges |
+----------+----------+             +----------+----------+
           |                                   |
           v                                   v
+---------------------+             +---------------------+
| Canonical ERP       |             | Canonical Cycles    |
| production_orders   |             | machine_cycles      |
| shifts              |             | hypertable          |
+----------+----------+             +----------+----------+
           |                                   |
           +-----------------+-----------------+
                             v
                  +----------------------+
                  | Reconciliation       |
                  | temporal join        |
                  | confidence + issues  |
                  +----------+-----------+
                             |
                             v
                  +----------------------+
                  | Analytics            |
                  | CAGG, reports, IA    |
                  +----------------------+
```

## Ordre de correction recommande

1. Stabiliser Docker/DB et credentials.
2. Ajouter la couche staging et les contraintes minimales.
3. Corriger timestamp Engel et date Arburg.
4. Integrer l'import ERP dans `production_orders` et `shifts`.
5. Rendre l'insertion idempotente par ligne.
6. Deplacer la reconciliation dans une etape dediee.
7. Ajouter logs structures et compteurs d'import.
8. Aligner les tests E2E avec cette architecture.
9. Etendre le dictionnaire EUROMAP/OPC UA.
10. Ajouter performance `COPY` et tests gros volume.

## Definition de "pret pour correction"

Avant de toucher au code, on doit etre d'accord sur ces decisions :

- Le pipeline doit-il rester en scripts Python autonomes ou devenir un package CLI propre ?
- Doit-on garder Redis maintenant, ou le repousser apres l'ingestion batch fiable ?
- Quelle timezone usine utiliser par defaut ?
- Quelle cle d'idempotence par cycle choisir ?
- Les fichiers ERP sont-ils la source principale des OF, ou les OF peuvent-ils venir aussi des metadonnees machine ?

Ma recommandation : garder des scripts Python autonomes pour le livrable, mais structurer le code comme un package interne avec modules `profile`, `parse`, `stage`, `validate`, `load`, `reconcile`.
