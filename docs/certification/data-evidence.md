# Données : démonstration limitée et reproductible

État du 9 septembre 2026, base `01fcb4fa8daa8261ca34cf2e44171a4d7836af5b`. Aucun verdict de compétence.

## Reproduction hors réseau

Depuis la racine, Python 3 et bibliothèque standard suffisent pour le démonstrateur :

```sh
python3 scripts/certification/data_demo.py > /tmp/iddrv-synthetic-data.json
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_certification_data*.py' -v
```

Le dernier test requiert Pydantic de l'environnement backend existant. Ne pas installer globalement. Lors de cette intervention, utilisation en lecture de `.venv/bin/python` du dépôt principal avec écriture de bytecode désactivée : **5 tests réussis**, aucun conftest chargé, aucune connexion réseau/DB externe. La SQLite temporaire est créée et supprimée par `TemporaryDirectory`, sans lecture de credentials.

Deux sources **synthétiques embarquées**, CSV machines et JSON sites, sont lues, normalisées et importées dans une projection SQLite du couple `sites/machines` de `db/init.sql`. Ce n'est ni l'exécution du DDL PostgreSQL/TimescaleDB, ni le repository applicatif, ni un endpoint HTTP. Le payload est validé par le vrai modèle `backend.app.schemas.Site`. Aucune extraction web, scraping ou big data n'est revendiquée.

Règles : espaces périphériques retirés ; identifiants entiers positifs ; référence obligatoire ; doublon strict écarté ; identité conflictuelle ou site inexistant font échouer l'import transactionnel. Les lignes rejetées conservent numéro et motif sans données personnelles. Les SHA256 portent sur les sources littérales exactes. Résultat observé : 5 lignes CSV, 3 importées, 1 référence vide rejetée, 1 doublon écarté ; site 1 = 2 machines, site 2 = 1. Le JSON est la sortie sauvegardable ; aucune donnée d'entreprise n'est utilisée.

SQL : `WHERE s.id=?` borne le site et évite l'interpolation ; `LEFT JOIN` conserve un site vide ; `COUNT(m.id)` donne zéro plutôt qu'un faux un ; `GROUP BY` définit une ligne par site. L'index `machines_site` sert la jointure. Le plan observé utilise la clé primaire sites et l'index couvrant machines ; un tri temporaire demeure. Aucun gain de latence ou comportement PostgreSQL n'est déduit de ce plan miniature.

## Réutilisation des pièces locales, sans les modifier

Lecture seule de `/Users/soufianehamzaoui/Desktop/EPSI/ProjetSeptembre/Preuve-manquante/donnees/README.md` : décrit parseur ERP réel sur six lignes synthétiques, SQL contextualisée **non exécutée**, routeur réel avec session/repository simulés. Ces résultats historiques ne sont pas réexécutés ici et ne deviennent pas preuves de service complet. Ne pas transporter les XLSX/PNG/environnements volumineux. La requête `extraction_contextuelle.sql` reste candidate pour une base PostgreSQL/Timescale isolée, schéma et migrations appliqués, avec paramètres site/machine/temps et résultats/EXPLAIN archivés. Sa présence ne suffit pas.

Blocages C1/C2 : aucune source de scraping autorisée, aucun système big data dédié et aucune extraction de ces sources établie dans le périmètre. Faire fournir accès, règles d'usage/confidentialité, volume et contrat avant implémentation. SQLite ne les remplace pas. C4/C5 : installation complète, import par le vrai repository et lecture authentifiée persistée restent à exécuter en bac à sable.
