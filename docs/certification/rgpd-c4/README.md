# C4 — dossier minimal à présenter

## Périmètre retenu

À la demande du porteur du projet, ce chantier se limite aux quatre pièces ci-dessous. Les annexes et tests déjà produits sont conservés comme justificatifs, pas comme un programme supplémentaire à réaliser.

| Pièce minimale | Contenu attendu | Document existant |
|---|---|---|
| Modélisation | Modèles Merise cohérents avec la base présentée, choix du SGBD | [Modèles](modeles.md) |
| Installation et import | Commandes, dépendances, création de la base/API et insertion réellement vérifiées | [README du projet](../../../README.md), preuves des chantiers données/CI à relier |
| Registre | Traitements réellement concernés, données/finalités, responsable, destinataires, justification et conservation renseignés sans invention | [Registre](registre.md) et [fiches](registre.json) |
| Tri/conservation | Quoi conserver, supprimer ou anonymiser, quand et par qui ; exceptions et fréquence | [Procédure](conservation-exercice.md) |

La grille accepte des traitements de tri **automatisés ou non** : aucun ordonnanceur ni outil de purge de production n'est ajouté. Le simulateur SQLite est une annexe pédagogique, pas une condition supplémentaire ni une preuve de purge de la base applicative. Les décisions encore inconnues restent visibles ; ce périmètre minimal ne vaut pas attestation juridique.

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

## Les quatre points à terminer

- [ ] Relire les modèles et couvrir les données de la base effectivement présentée ; le dictionnaire actuel est ciblé, pas exhaustif.
- [ ] Rattacher une preuve d'installation API/base et d'import au commit présenté, avec commandes et dépendances ; réutiliser les exécutions des autres chantiers au lieu de les refaire sans besoin.
- [ ] Compléter et valider les champs inconnus du registre pour le contexte réel ou fictif déclaré : responsable, finalités/justifications, destinataires et durées. Ne pas présenter une décision fictive comme celle d'une entreprise réelle.
- [ ] Valider une procédure de tri applicable avec fréquence, responsable et exceptions. Une procédure manuelle documentée est possible ; aucune suppression réelle n'est autorisée par ce dossier.

**Hors chantier immédiat :** automatisation de purge de production, refonte des migrations, campagne complète d'exercice des droits et restauration multi-supports. Ces travaux ne sont pas déclarés inutiles juridiquement : leur nécessité dépend du contexte réel, mais ils ne sont pas ajoutés automatiquement à la liste de développement C4.

Les triggers immuables et références auteur doivent être pris en compte dans toute procédure appliquée. Aucun contournement n'est livré. C4 reste incomplet tant que les quatre pièces et les critères détaillés ci-dessus ne sont pas effectivement justifiés.
