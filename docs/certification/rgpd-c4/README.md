# Chantier C4 RGPD — pièces de travail

Référence inspectée `59a4846b`, branche de départ iddrv-pilot. Aucune compétence auto-validée, aucune attestation de conformité exhaustive. Aucun schéma, migration, serveur, collecteur, CI, frontend ou modèle ML modifié. Aucun accès base utilisateur, secret ou donnée réelle.

- [Modèles Merise textuels, MLD, MPD et dictionnaire ciblé](modeles.md)
- [Index reproductible des sources SQL](sql-source-index.json) : 56 tables déclarées, 24 fichiers (init, 22 migrations, setup), empreintes SHA-256 ; pas catalogue d'une base active.
- [Registre expliqué](registre.md) et [8 fiches structurées](registre.json)
- [Politique proposée, procédure et exercice synthétique](conservation-exercice.md)
- [Script simulateur](../../../scripts/certification/rgpd/synthetic_purge.py) et [tests](../../../tests/test_certification_rgpd.py)

## Traçabilité exacte des sous-critères C4

Sources lues : référentiel RNCP 37827, extraction `03.txt` pages 4–5 ; grille individuelle `06.txt` pages 4–5 du dossier temporaire d'audit communiqué. Les formulations ci-dessous reprennent le référentiel (la grille reprend les mêmes attentes). Les statuts sont des observations de livrables, **pas Acquis/Non acquis**.

| Sous-critère | Pièces / état observé dans ce lot |
|---|---|
| « Les modélisations des données respectent la méthode et le formalisme Merise. » | Présent : entités, associations et min/max, MLD séparé du MPD ; noyau/RGPD complétés. **Incomplet** pour tous attributs/associations des 56 tables ; relecture Merise humaine requise. |
| « Le modèle physique des données est fonctionnel : il est intégré avec succès lors de la création de la base de données, sans erreur. » | Autorité identifiée : init + 001–022 + setup. Index statique testé ; **non vérifié** ici sur PostgreSQL/Timescale neuf. SQLite ne constitue pas cette preuve. |
| « La base de données est choisie au regard de la modélisation des données et des contraintes du projet. » | Présent : justification transactions, FK composites, JSONB, séries temporelles, contraintes Timescale et alternative SQLite/documentaire dans modeles.md. Décision et dimensionnement effectif à confirmer. |
| « La reproduction des procédures d’installation décrites (base de données et API) a pour résultat un système conforme aux objets techniques attendus.. » | Procédures existantes [README racine](../../../README.md), [opérations](../operations.md), setup/Compose repérés ; **non reproduit** dans ce lot. À relier aux preuves isolées du chantier CI/deploy, sans les présumer. |
| « Le script d’import fourni est fonctionnel : il permet l’insertion des données dans le système mis en place. » | Chemins métier existants ingestion et upload repérés ; **non testé** ici. L'import de fixture SQLite est testé mais n'est pas l'import métier C4. Coordination avec chantier C1/C2. |
| « La documentation technique du script d’import est versionné à la racine du même dépôt Git que celui utilisé pour le script d’import. » | [README racine](../../../README.md), [preuves données](../data-evidence.md) présents ; **incomplet à confirmer** : couverture du script d'import retenu et exigence racine, hors exclusivité C4. Aucun README racine modifié. |
| « Les documentations techniques des script couvrent les parties suivantes : les dépendances nécessaires pour la réutilisation des scripts (langages, dépendances externes, etc) ; les commandes pour l’exécution des scripts. » | **Présent et testé pour simulateur C4** : Python standard/SQLite, commandes dry-run/exécution/tests/index. Documentation import métier à compléter/relier par propriétaire C1/C2 ; ne pas assimiler simulateur à import métier. |
| « Le registre des traitements de données personnelles intègre l’ensemble des traitements de données personnelles impliqués dans la base de données. » | Présent : huit fiches, comptes/sessions/IP/logs/imports/ERP/télémétrie/feedback/audit/exports/sauvegardes ; **incomplet** tant que inventaire réel, responsables, bases, destinataires et durées non approuvés. |
| « Les procédures de tri des données personnelles pour la mise en conformité de la base de données avec le RGPD sont rédigées. » | Présent : minimisation, qualification, lot, exceptions, intégrité, fichiers, restauration ; **testé uniquement sur fixture synthétique réduite**. Adaptateur réel absent volontairement. |
| « Les procédures de tri détaillent les traitements de conformité (automatisés ou non) à appliquer ainsi que leur fréquence d’exécution. » | Présent : tableau de fréquences proposées, manuel et simulation automatisée. Cadences finales/autorité/ordonnanceur **non approuvés et non activés**. |

## Vérification locale

Commandes depuis la racine (aucune installation nécessaire) :

```sh
python3 -m unittest discover -s tests -p 'test_certification_rgpd*.py' -v
python3 scripts/certification/rgpd/schema_inventory.py
git diff --check
```

Résultat de cette session : **11 tests réussis** (dates UTC/frontière, politique fail-closed, dry-run sans écritures après seed, suppression précise, autre site, FK, audit/référence croisée, rollback, confirmation, sorties expurgées, index sources/liens docs). Les commandes CLI dry-run et exécution synthétique ont également été exécutées : candidats 1 dossier/1 fichier, retenu 1 dossier audité, avant 6/6, après dry-run 6/6 et exécution 5/5. `git diff --check` sans erreur. Les tests d'index doivent être régénérés/revus si le schéma autorité change, pas neutralisés pour accepter une divergence.

## Checklist de clôture humaine / prochaine preuve

- [ ] Nommer responsable de traitement, propriétaire de chaque fiche et contact droits/DPO éventuel.
- [ ] Approuver finalités/bases juridiques, catégories/personnes, analyse d'impact requise ou non avec motif.
- [ ] Recenser hébergeur réel, destinataires/exportataires, sous-traitants, contrats, localisations/transferts et garanties.
- [ ] Arrêter durées active/archive, déclencheurs, exceptions et fréquence pour chaque fiche ; pas de valeur implicite.
- [ ] Vérifier habilitations réelles, comptes partagés, accès SQL/fichiers/sauvegardes, révocation multi-site, sécurité TLS/cookies et logs.
- [ ] Compléter/revoir MCD/MLD/dictionnaire exhaustifs et tester MPD 001–022 sur PostgreSQL/Timescale neuf ; conserver preuve catalogue/contraintes expurgée.
- [ ] Relier import métier versionné et documentation racine, commandes, dépendances et test d'insertion réel synthétique (propriétaire C1/C2).
- [ ] Relier installation API/DB reproduite aux preuves CI/deploy sans double intervention sur ressources.
- [ ] Concevoir adaptation de tri réelle (si autorisée) avec propriétaire backend : schéma courant, triggers, snapshots, agrégats et copies fichiers ; pas de changement autorisé par ce simulateur.
- [ ] Tester restauration synthétique multi-supports, non-réintroduction, exercice des droits et incident de confidentialité ; approuver le lot réel séparément.

**Besoin remonté au parent :** les triggers immuables, les références auteur obligatoires et les dépendances historiques ne permettent pas une purge universelle. Une stratégie de dissociation/pseudonymisation ou un changement de schéma éventuel nécessite arbitrage responsable/juridique + architecture ; aucun contournement livré. Le chantier ouvre C4 mais ne le déclare pas satisfait.
