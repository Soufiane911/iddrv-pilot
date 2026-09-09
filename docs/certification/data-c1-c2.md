# C1/C2 — extraction indépendante, preuves bornées

Base vérifiée : `59a4846b`. Exécution réelle le **9 septembre 2026**, sans verdict « acquis ». Aucun `AGENTS.md` trouvé dans le worktree ni ses parents. Skills backend-engineer et data-scientist lus. Aucun changement ingest, ML, API, UI, summary6, déploiement ou dépôt principal.

## Critères et périmètre

Référentiel officiel `03.txt`, pages imprimées 1–3, grille `06.txt`, pages 2–3 : C1 exige contexte complet (acteurs, objectifs, environnement, contraintes, budget, organisation, planification), spécifications outils/services/langages/accès, périmètre extraction et agrégation complet, récupération effective, point de lancement/connexions/erreurs/fin/sauvegarde, versionnement accessible, **mix REST, fichier, scraping, SGBD et système big data**. C2 exige requêtes exécutées sur SGBD **et** système big data, documentation des sélections/filtres/conditions/jointures et optimisations. Aucun de ces critères n'est remplacé par la seule présence d'un script.

Ce lot prolonge `data-evidence.md` et `data_demo.py`, sans refaire ni modifier leur microdémo SQLite. `criteria-matrix.md` est un état antérieur : la présente pièce apporte PostgreSQL/Timescale exécuté et collecte HTTP, mais ne clôt pas C1/C2.

### Ancrage métier et séparation

`ingest/ingest_pipeline.py` orchestre profiling → loader/mapper → passeport SHA → staging/rejets → rapprochement ERP/cycles → insertion, strictement par site. `db/init.sql` contient sites, machines et hypertable cycles, avec index machine/temps. Les migrations 013/015/017 portent déclarations, historique de contexte et identité de cycle. Les scripts de ce lot **ne sont pas branchés sur cette chaîne**, ne lisent pas sa configuration DB et n'importent aucune donnée externe en production.

Lecture seule des pièces `Preuve-manquante/donnees/README.md` et `extraction_contextuelle.sql` du dépôt principal : six lignes ERP synthétiques et requête historique non exécutée. Cette dernière, incluant connaissance temporelle du contexte et révisions, **reste non exécutée** ici. La nouvelle requête porte sur une projection explicite sites/machines/cycles ; elle n'est ni cette requête historique ni une migration complète de l'application.

Objectif de collecte : caractériser les cycles valides par machine et heure, conserver les machines sans cycle, exclure un autre site et les bornes temporelles hors fenêtre. Utilisateurs visés : développeur ingestion et analyste ; responsabilités réelles, budget métier et planning restent à confirmer par le commanditaire. Coût de ce lot : aucune installation massive, image Docker déjà locale, mémoire DB 512 MiB, CPU 1, tmpfs 256 MiB ; DuckDB 128 MiB / 1 thread. Pas de budget financier inventé.

## Contrat opérateur et sécurité

Point d'entrée : `scripts/certification/extract_sources.py`. Python **3.13.9** (bibliothèque standard pour fichiers et HTTP) ; dépendances optionnelles déjà disponibles ici : psycopg **3.3.4**, DuckDB **1.4.4**, Docker **28.5.1**. DuckDB est optionnel : seul le test d'intégration analytique est ignoré avec motif explicite s'il est absent ; les tests purs, notamment les bornes temporelles, restent exécutés sans lui. Dépendance dédiée : `scripts/certification/requirements-analytics.txt` (`duckdb==1.4.4`), sans ajout au runtime principal ; pour le bac DB, psycopg et l'image Timescale locale sont requis. Aucune dépendance installée pendant ce lot. Chaque exécution crée un **nouveau** répertoire privé ; échec code 1 et `error.json` à code expurgé, réussite `records.jsonl` UTF-8 canonique et `manifest.json` version 1. Champs projetés explicitement ; aucune fusion silencieuse de sources hétérogènes.

Exemple de contrat local (chemin à adapter, ne pas utiliser de fichier privé) :

```json
{"id":"synthetic-machines","kind":"csv","fields":["id"],"path":"/tmp/synthetic-machines.csv","local_fixture":true,"max_bytes":1048576,"max_rows":1000}
```

Kinds : CSV à en-tête exact ; JSON tableau d'objets ; REST `{ "items": [...], "next": URL-ou-null }` ; HTML **premier tableau**, en-tête exact. JSON distant peut être une API REST retournant un tableau ; pas de pagination implicite, la portée doit être explicitement limitée côté URL. HTML sans tableau, imbriqué, en-tête ou largeur incorrects : refus. Pas de JavaScript ni navigation automatique.

HTTP : URL et chaque page suivantes doivent figurer intégralement dans `allowed_urls`. HTTPS obligatoire, sauf `local_fixture:true` qui impose uniquement des IP loopback. Résolution DNS vérifiée (toutes les IP publiques ou toutes loopback), connexion épinglée à l'IP validée, vérification TLS du nom, ni proxy implicite ni redirection. Pas d'API publique pour ce contrat, uniquement opérateur de confiance. Ne jamais placer de secret dans URL/contrat/champ projeté ; `token_env` peut désigner une variable explicitement fournie, jamais découverte. Manifestes : identifiant opérateur, date UTC de collecte (pas date métier), comptes, octets/SHA256 de chaque réponse brute, SHA256 du JSONL ; **ni URL, chemin local, token, corps d'erreur, ni DSN**. Conserver le contrat public à côté des preuves pour associer identifiant et source ; ne pas attribuer une fixture à une source industrielle.

Quotas : 1 MiB, 1000 lignes, 3 pages, délai socket/lecture 5 s par défaut ; plafonds 10 MiB, 100000 lignes, 20 pages, 30 s. Dépassement et boucle de pagination échouent, sans prétendre avoir tout récupéré ; 401/403/429/3xx sont des erreurs sans retry. Pas de compression acceptée. Limites restantes : résolution DNS et réception des en-têtes ne disposent pas d'un deadline global indépendant ; lancer le CLI sous un superviseur avec budget total pour toute source non maîtrisée. L'opérateur valide licence, robots/règles d'usage, champs non personnels et cadence avant toute collecte périodique ; aucun ordonnanceur installé ni autorisation générale supposée.

## Exécutions réellement observées

Preuves locales expurgées : `/tmp/iddrv-c1c2-f7bb05e3` (résultats non committés). Les fixtures HTTP sont servies en loopback par les tests, distinctes des deux collectes publiques suivantes, sans authentification :

| Source/portée auxiliaire | Résultat réel | SHA256 réponse brute |
|---|---|---|
| `https://api.github.com/repos/python/cpython/tags?per_page=1`, champ `name`, veille du runtime Python, pas télémétrie | 2026-09-09T14:13:12Z ; HTTP 200 ; 423 octets ; 1 ligne | `12e981acd315d0e98e639292d52cdc405cef73c4d1b6f68de5d387d438179ed2` |
| `https://docs.python.org/3/library/datetime.html`, premier tableau Operation/Result, règles de calcul temporel utiles à ingestion | 2026-09-09T14:13:13Z ; HTTP 200 ; 422679 octets ; 15 lignes | `91dc8effbf8e65c063e47c5e1f12185769852db0eaa7ce08e2d968d2a86c18c5` |

Classification `public_auxiliary_not_industrial`. Aucune licence de réutilisation générale ni actualité permanente revendiquée. Seulement les compteurs et empreintes sont versionnés. Une requête exploratory `geo.api.gouv.fr/communes?code=59350&fields=nom,code` a retourné **404** ; aucune donnée géographique collectée. La page Python a été téléchargée deux fois (inspection puis collecte), sans crawl.

Rejouer les contrats publics conservés dans le dossier local, ou les reconstruire avec `id`, `kind=json/html`, `fields`, `url`, `allowed_urls:[url]`, `classification=public_auxiliary_not_industrial` :

```sh
python scripts/certification/extract_sources.py /tmp/iddrv-c1c2-f7bb05e3/runtime-tags-contract.json --output /tmp/iddrv-c1c2-tags-new
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_certification_sources*.py' -v
PYTHONDONTWRITEBYTECODE=1 python -m scripts.certification.sources.sandbox --output /tmp/iddrv-c1c2-db-new
ruff check scripts/certification/extract_sources.py scripts/certification/sources tests/test_certification_sources.py
```

Résultats : **10 tests réussis**, aucun skip ; Ruff `All checks passed!`. CLI fichier également exécuté : `{"status":"ok","source_id":"synthetic-file","rows":1}` ; `git diff --check` sans erreur, aucun conteneur `iddrv-c1c2-*` restant après nettoyage. CSV vide/en-tête et JSON vide, sources malformées, pagination/limites/cycle, projection excluant un token, manifestes sans secrets, 401, 429, redirection refusée, timeout transport simulé, isolation URL, injection SQL rejetée, vraie requête DuckDB. Premier essai DuckDB en échec : inférence TIMESTAMP naïve + timezone Europe/Paris décalait la borne ; correction explicite UTC, test réel ensuite réussi. Le timeout réseau testé par exception simulée n'est pas un test de lenteur des en-têtes.

### PostgreSQL/TimescaleDB effectivement exécuté

`sources/sandbox.py` n'utilise que l'image locale `timescale/timescaledb:2.28.2-pg16`, sans pull. Conteneur unique `iddrv-c1c2-<uuid>`, port aléatoire **127.0.0.1**, tmpfs sans volume hôte, label propriétaire contrôlé avant suppression dans `finally`. Auth trust uniquement dans ce bac synthétique éphémère, pas modèle de déploiement. Aucune commande compose/prune ni nettoyage d'autres conteneurs.

Résultat : PostgreSQL **16.14**, Timescale **2.28.2**, conteneur supprimé. Projection synthétique : 2 sites, 3 machines, 5 cycles. Paramètres site 1 et `[2026-09-01T00:00Z, 01:00Z[` ; deux lignes : machine 1 = **2 cycles, moyenne 15 s**, machine 2 = **0 cycle, moyenne NULL**. Cycle invalide 999 s, cycle à 01:00 et autre site exclus. Site 999 = zéro ligne ; injection `1 OR 1=1` rejetée. Transaction READ ONLY, statement_timeout 5 s, paramètres psycopg, limite +1 détectant une troncature.

SQL `sql/cycles.sql` : jointure gauche avec filtres temporels/qualité dans ON pour préserver les machines vides ; `COUNT(c.time)` et non COUNT(*) ; granularité machine/heure, pas de somme ERP par cycle. Index `(machine_id,time)`, hypertable et prédicats sans transformation de la colonne temporelle favorisent l'élagage de chunks et la recherche sélective. **EXPLAIN ANALYZE BUFFERS réel préfère Seq Scan du minuscule chunk, Hash Right Join et tri/agrégat** : aucun gain index ou capacité industrielle déduit. Rapport DB SHA256 `b4d0c0b5a1da408ba9c88ab8619502f0822d4a6d245f608f9e1cc0366d19d7a5` ; horodatage/plan pouvant changer au rejeu.

### Analytique locale et big data : frontière explicite

DuckDB **1.4.4** réellement disponible et exécuté par test sur **3 lignes JSONL synthétiques**, filtre site/qualité/temps et agrégat : site 1 = 2 cycles, moyenne 10 s. Requête `sql/analytics.sql`, paramètres liés, UTC, mémoire bornée et extensions automatiques désactivées. **Ce n'est pas une source big data ni un cluster distribué ; aucune qualification jury supposée. SQLite ne remplace pas non plus cette exigence.**

Spark/pyspark/spark-submit absents. `sources/spark.py` + `sql/spark_cycles.sql` : adaptateur **NON EXÉCUTÉ**, session Spark >=3.4 fournie explicitement, lecture d'une partition Parquet autorisée, SQL nommé, vue temporaire nettoyée, borne résultat +1. Avant exécution : obtenir moteur/source réellement disponibles, valider schéma (time TIMESTAMP, site_id/machine_id, cycle_time_s, data_quality_status), autorisations et volumes de partition ; imposer deadline/cancellation et quotas cluster dans le superviseur ; configurer UTC ; appeler `extract(session, partition, site, from_utc, to_utc)` ; archiver version, plan EXPLAIN, comptes attendus/obtenus et manifestes SHA. Le LIMIT résultat ne borne pas le volume scanné : ne pas lancer sur un lac entier. Ne pas installer Spark massivement pour fabriquer une preuve nominale.

## Correctifs de revue (base `54156891`)

- Sandbox : inspection du nom unique dans `finally`, même si `docker run` crée le conteneur puis échoue. Suppression seulement si le label propriétaire correspond ; label étranger ou inspection impossible : aucune suppression. Tests simulés création suivie d'échec, propriétaire étranger et conteneur absent ; Docker/Timescale non rejoués pendant cette revue.
- Spark : `newSession()` isole timezone UTC et vue temporaire de chaque extraction ; aucun `stop()` (SparkContext partagé avec l'appelant). Tests avec faux Spark : vue préexistante et timezone Europe/Paris conservées après succès, exception et deux extractions concurrentes. **Spark réel toujours NON EXÉCUTÉ** ; ces doubles ne prouvent ni compatibilité moteur ni comportement cluster.
- PostgreSQL, Spark et DuckDB partagent la validation stricte avant accès source/SQL : ISO 8601 ou datetime avec fuseau, conversion UTC, début strictement antérieur à fin ; None, naïf, égal/inversé rejetés. Les offsets équivalents sont normalisés, pas comparés lexicalement. Validation pure testée même avec import DuckDB interdit ; intervalle avec offsets également vérifié sur DuckDB réel.
- Vérification revue : 18 tests sources réussis avec DuckDB **1.4.4**, aucun skip ; processus Python séparé interdisant l'import DuckDB : 18 tests, **17 réussis et 1 skip explicite** (intégration seulement). Les 5 tests `test_certification_data_demo.py` réussissent aussi. Ruff et `git diff --check` sans erreur. Aucune installation ni accès réseau/production pendant la revue.

Reproduction de l'intégration optionnelle dans un environnement isolé (commande opérateur, non exécutée ici ; installation nécessitant un index autorisé ou des wheels locales) :

```sh
python3 -m venv /tmp/iddrv-c1c2-analytics-venv
/tmp/iddrv-c1c2-analytics-venv/bin/python -m pip install -r scripts/certification/requirements-analytics.txt
PYTHONDONTWRITEBYTECODE=1 /tmp/iddrv-c1c2-analytics-venv/bin/python -m unittest discover -s tests -p 'test_certification_sources*.py' -v
```

Limites des fixtures inchangées : HTTP loopback, projection SQL minuscule, trois lignes JSONL et faux Spark ne constituent ni source industrielle, ni benchmark, ni preuve de récupération big data. Les observations HTTP publiques et PostgreSQL ci-dessus sont historiques, non renouvelées par cette revue.

## Restes précis sans bloquer le livré

1. Source industrielle privée autorisée, contrats réels, règles de confidentialité/cadence et preuve récupération exhaustive restent à obtenir.
2. Source et moteur big data qualifiables, exécution réelle de l'adaptateur, temps/quotas/plan et provenance restent à produire.
3. Exécuter la requête contextuelle historique sur schéma applicatif complet migré ; ce lot n'en revendique pas la validation.
4. Définir agrégation finale multi-sources pertinente et validée métier : les tables de documentation/runtime ne doivent jamais rejoindre silencieusement les cycles.
5. Compléter acteurs/budget/organisation/planning réels et vérifier accès Git distant après revue/intégration humaine ; aucun push effectué ici.

C1/C2 restent **partiellement étayés**, pas auto-attribués. Les résultats PostgreSQL et HTTP ne deviennent ni preuve d'exploitation ni benchmark de volume.
