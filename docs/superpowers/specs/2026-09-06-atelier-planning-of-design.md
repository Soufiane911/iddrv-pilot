# Atelier et planning OF multi-presse — Spécification

**Statut :** proposé pour validation utilisateur  
**Date :** 6 septembre 2026  
**Périmètre :** création du parc depuis l'Atelier et suivi hebdomadaire type Excel

## 1. Décisions métier validées

- Un site peut être créé et utilisé sans import ERP initial.
- L'installation est locale.
- Une passerelle API locale représente une source au niveau du site et agrège plusieurs boîtiers de presses.
- Les événements sont transmis dès leur création.
- Une presse transmet un identifiant technique stable, le numéro d'OF saisi sur la presse, le compteur de cycle, l'horodatage et les paramètres process disponibles.
- Le numéro OF ERP définitif est connu au moment de la planification et doit rester une chaîne afin de préserver ses zéros initiaux.
- Un même OF peut être produit simultanément sur plusieurs presses.
- L'ERP est importé plus tard. Il contient une ligne par presse et les quantités de ces lignes sont propres à chaque presse et additionnables au niveau de l'OF.
- Les cycles machine ne permettent pas de connaître les pièces bonnes ou rebutées. Avant l'ERP, ces valeurs sont inconnues, jamais égales à zéro par défaut.

## 2. Objectifs

1. Faire de l'Atelier le point d'entrée naturel pour créer un site, ajouter ses presses, connecter sa passerelle et mapper les identifiants détectés.
2. Permettre de planifier à l'avance un OF sur une ou plusieurs presses dans une grille hebdomadaire proche d'Excel.
3. Relier immédiatement les cycles au bon OF et à la bonne presse grâce aux identifiants transmis par la source.
4. Enrichir ensuite chaque ligne OF-presse avec les déclarations ERP, sans doublon ni perte d'historique.
5. Conserver les événements même lorsqu'une presse ou un OF n'est pas encore configuré.

## 3. Hors périmètre du premier MVP

- Optimisation automatique du planning et calcul de capacité.
- Glisser-déposer des créneaux et copier-coller multi-cellules depuis Excel.
- Écriture du planning vers l'ERP ou vers les presses.
- Déduction de pièces bonnes, de rebuts ou de qualité depuis le nombre de cycles.
- Gestion cloud et passerelles redondantes.
- WebSocket obligatoire : un rafraîchissement toutes les 2 à 5 secondes suffit d'abord pour l'interface.
- Qualification automatique d'un paramètre process comme bon ou mauvais sans limites métier configurées.

## 4. État actuel à prendre en compte

La branche principale contient encore surtout le prototype d'ingestion. Le frontend, FastAPI et la création de sites les plus avancés sont actuellement des changements non intégrés dans le worktree `.worktrees/report-alignment`.

Le travail d'implémentation de cette spécification doit commencer après intégration et stabilisation de ce travail. Il devra adapter, plutôt que dupliquer :

- `backend/app/api/site_management.py` ;
- `backend/app/api/machine_management.py` ;
- `backend/app/api/machine_connections.py` ;
- `frontend/src/pages/SitesPage.tsx` ;
- `frontend/src/pages/WorkshopPage.tsx` ;
- `frontend/src/components/workshop/` ;
- l'assistant ERP existant dans `frontend/src/components/imports/`.

Le modèle historique doit être corrigé : `production_orders.machine_id` impose actuellement une seule presse par OF, et les valeurs par défaut de qualité machine peuvent inventer une pièce bonne.

## 5. Architecture cible minimale

```text
Presses et boîtiers
        |
        | événements de cycle immédiats
        v
Passerelle locale du site
        |
        | API push authentifiée + retry durable
        v
Backend IDDRV
  - registre idempotent des événements
  - mapping source vers presse
  - rapprochement OF + presse
        |
        v
PostgreSQL / TimescaleDB
        |
        +--> Atelier : parc et collecte
        +--> Planning hebdomadaire
        +--> Import et rapprochement ERP
```

La passerelle est une **source du site**, pas une propriété répétée sur chaque presse. Le frontend communique uniquement avec le backend IDDRV, jamais directement avec les boîtiers ou la passerelle.

## 6. Modèle métier

### 6.1 Site

Le site possède un nom, un fuseau horaire et un état actif/archivé. L'ERP n'est pas requis à sa création.

### 6.2 Presse

La presse est un équipement métier du site. Elle possède :

- un nom obligatoire ;
- un code atelier obligatoire et unique dans le site ;
- une référence ERP facultative, unique dans le site lorsqu'elle existe ;
- des métadonnées facultatives : marque, modèle ;
- un état actif/inactif/archivé.

Une presse ayant de l'historique est archivée, jamais supprimée physiquement.

### 6.3 Source de site et mapping

Une source représente une passerelle authentifiée. Elle possède un identifiant, un secret rotatif, un état et une date de dernière communication.

Un mapping relie dans le temps :

```text
source + external_machine_id -> presse IDDRV
```

Un changement de mapping ferme l'association précédente et en crée une nouvelle. Les événements reçus avant mapping restent stockés dans une file « À rapprocher » et sont rejoués après validation.

### 6.4 OF, affectations et créneaux

- **OF** : identité globale dans un site, unique par `site + numéro OF normalisé`.
- **Affectation OF-presse** : relation entre un OF et une presse. Un OF peut en avoir plusieurs en parallèle.
- **Créneau planifié** : période prévue d'une affectation. Une affectation peut avoir plusieurs créneaux si la production est interrompue puis reprise.

Aucune quantité n'est saisie manuellement dans le planning MVP. Elle vient exclusivement de l'ERP.

### 6.5 Événements et cycles

Le reçu brut d'un événement est conservé avant toute transformation. Sa clé d'idempotence est `source + event_id`.

Chaque cycle matérialisé conserve :

- source et événement d'origine ;
- site et presse ;
- OF transmis par la presse ;
- affectation OF-presse résolue, si elle existe ;
- créneau résolu, si possible ;
- compteur, horodatage et paramètres process ;
- méthode et état de rapprochement.

`good_parts`, `scrap_flag` et toute qualité pièce restent `NULL/unknown` lorsque la source ne les fournit pas.

### 6.6 Déclaration ERP par presse

Une déclaration ERP versionnée appartient à une affectation OF-presse. Elle contient les quantités et indicateurs de cette ligne ERP. Une nouvelle importation remplace la version courante sans effacer les précédentes.

Le total d'un OF est la somme des versions courantes de ses différentes presses. Un réimport du même snapshot ne doit jamais doubler cette somme.

## 7. Règles de rapprochement

### 7.1 Cycle reçu

Ordre de résolution :

1. identifier le site depuis la source authentifiée ;
2. identifier la presse avec le mapping historique de `external_machine_id` à l'heure de l'événement ;
3. normaliser le numéro OF par suppression des espaces périphériques et comparaison insensible à la casse, sans supprimer les zéros initiaux ;
4. rechercher l'OF dans ce site ;
5. rechercher l'affectation de cet OF à cette presse ;
6. rechercher éventuellement le créneau contenant l'horodatage.

La jointure exacte `site + OF + presse` est prioritaire. La fenêtre temporelle ne doit plus choisir automatiquement l'OF ; elle ne sert qu'à formuler une suggestion lorsque la référence est absente ou incorrecte.

### 7.2 Cas incomplets

- **Presse non mappée :** événement conservé en attente.
- **OF inconnu :** événement conservé avec son OF brut et action « créer l'OF ».
- **OF connu mais presse non planifiée :** rattachement à l'OF, anomalie visible et action « ajouter cette presse ».
- **OF presse différent du planning :** ne pas modifier la donnée brute ; demander une résolution humaine.
- **Passerelle silencieuse :** afficher « collecte interrompue », jamais conclure automatiquement que la presse est arrêtée.

### 7.3 Import ERP

Chaque ligne ERP est rapprochée par :

```text
site + numéro OF + référence ERP de la presse
```

L'import :

1. retrouve ou crée l'OF ;
2. retrouve ou crée l'affectation OF-presse ;
3. crée une nouvelle version de déclaration ERP ;
4. reprend les événements en attente de ce couple OF-presse ;
5. signale les doublons, presses inconnues et ambiguïtés avant confirmation.

Deux lignes identiques pour le même OF et la même presse dans un snapshot ne sont jamais additionnées silencieusement.

## 8. Parcours « créer correctement depuis l'Atelier »

### 8.1 Catalogue des sites

Route : `/sites`

Chaque carte affiche le nom, le fuseau, le nombre de presses, l'état de la collecte, le dernier cycle et les mappings en attente.

Actions :

- `Nouveau site` ;
- `Ouvrir l'atelier` ;
- `Continuer la configuration` ;
- `Archiver` pour un administrateur.

Le formulaire « Nouveau site » demande uniquement le nom et le fuseau. Après création, l'utilisateur est redirigé vers l'Atelier. L'import ERP n'est pas inclus dans ce premier formulaire.

### 8.2 Atelier vide

Route : `/sites/:siteId/workshop`

Afficher une checklist :

1. site créé ;
2. ajouter les presses ;
3. créer la passerelle ;
4. mapper les identifiants détectés ;
5. vérifier le premier cycle.

Actions visibles immédiatement :

- `Ajouter une presse` ;
- `Configurer la passerelle` ;
- `Importer l'ERP`.

### 8.3 Ajouter une presse

Le formulaire court demande le nom et le code atelier. La référence ERP, la marque et le modèle sont facultatifs. Après création, la presse existe immédiatement et peut être mappée plus tard.

### 8.4 Configurer la passerelle

Le formulaire crée une source `gateway_push`, génère un secret affiché une seule fois et fournit :

- l'URL locale de réception IDDRV ;
- l'identifiant de source ;
- le secret ;
- un exemple de configuration.

États : non activée, en attente, réception active, interrompue, authentification refusée, contrat invalide.

### 8.5 Mapper les presses détectées

Une table affiche chaque `external_machine_id`, sa première et dernière détection, son dernier OF, son compteur et le nombre d'événements en attente.

Actions :

- associer à une presse existante ;
- créer une presse puis l'associer ;
- ignorer une identité de test ;
- corriger un conflit ;
- rejouer les événements après mapping.

## 9. Planning hebdomadaire type Excel

Route : `/sites/:siteId/planning?week=YYYY-Www`

### 9.1 Forme de la grille

La grille utilise une table métier accessible avec colonnes figées et défilement horizontal. Elle ne cherche pas à reproduire toutes les fonctions d'Excel dans le MVP.

Le grain d'une ligne est un **créneau OF-presse**. Les lignes sont regroupables par numéro OF afin d'afficher un total global sans masquer le détail par presse.

### 9.2 Barre d'outils

- semaine précédente/suivante ;
- retour à la semaine courante ;
- fuseau du site ;
- filtres Presse, OF, état de collecte et état ERP ;
- dernière actualisation ;
- `Planifier un OF` ;
- `Importer l'ERP`.

### 9.3 Colonnes MVP

**Planification**

- état ;
- jour ;
- presse ;
- OF planifié ;
- OF observé sur la presse ;
- début prévu ;
- fin prévue ;
- note.

**Direct machine**

- état de la source ;
- cycles reçus dans le créneau ;
- premier et dernier cycle ;
- dernier compteur ;
- dernier cycle reçu/fraîcheur ;
- temps de cycle : dernier et moyenne ;
- couverture des paramètres.

**ERP par presse**

- état ERP ;
- date et version d'import ;
- quantité produite ERP ;
- bonnes pièces ERP ;
- rebuts ERP ;
- cycles ERP ;
- écart entre cycles machine et cycles ERP, seulement lorsque les deux valeurs existent.

Les paramètres process détaillés sont dans un panneau latéral ou un groupe de colonnes repliable, pas tous affichés par défaut.

Avant import, les cellules ERP affichent `En attente ERP` ou `N/D`, jamais `0`.

### 9.4 Planifier un OF multi-presse

Le formulaire demande :

- numéro OF ;
- une ou plusieurs presses ;
- début et fin prévus pour chaque presse ;
- note facultative.

La validation autorise le même OF sur plusieurs presses. Deux OF différents sur la même presse et le même intervalle déclenchent un conflit explicite. Une correction après réception de cycles crée une révision auditée.

### 9.5 États indépendants d'une ligne

Ne pas résumer toute la ligne par un seul voyant.

- **Planning :** planifié, en cours observé, terminé, annulé.
- **Collecte :** aucun cycle, réception active, interrompue, partielle.
- **Rapprochement :** concordant, OF différent, presse non planifiée, à rapprocher.
- **ERP :** en attente, rapproché, incomplet, conflit, correction disponible.

## 10. Composants frontend

Réutiliser les primitives existantes `StatePanel`, `EmptyPanel`, `StatusBadge`, `MetricCard`, `SectionTitle`, le shell, TanStack Query et l'assistant ERP.

Créer des composants métier explicites :

- `SiteSetupChecklist` ;
- `PressCatalogTable` et `PressFormDrawer` ;
- `GatewayCard` et `GatewayCredentialDialog` ;
- `DetectedPressMappingTable` ;
- `ProductionWeekToolbar` ;
- `ProductionPlanningGrid` ;
- `ProductionAssignmentEditor` ;
- `LiveCycleSummaryCell` ;
- `ProcessParametersPanel` ;
- `ErpPerPressStatus` ;
- `UnmatchedEventQueue`.

Éviter un composant générique géant `ComponentWizard` ou `DataGrid`. Les primitives visuelles peuvent être partagées, mais les règles Site/Presse/Source/OF restent dans leurs composants et services métier.

## 11. Contrats API principaux

Administration :

- `POST /api/v1/sites`
- `POST /api/v1/sites/{site_id}/machines`
- `PATCH /api/v1/machines/{machine_id}`
- `POST /api/v1/sites/{site_id}/sources`
- `POST /api/v1/sources/{source_id}/credentials`
- `POST /api/v1/sources/{source_id}/machine-mappings`
- `GET /api/v1/sources/{source_id}/detected-machines`

Ingestion :

- `POST /api/v1/ingestion/cycle-events`
- futur endpoint batch compatible avec les mêmes règles d'idempotence.

Planning :

- `GET /api/v1/sites/{site_id}/planning?week_start=YYYY-MM-DD`
- `POST /api/v1/sites/{site_id}/work-orders`
- `POST /api/v1/work-orders/{order_id}/allocations`
- `POST /api/v1/planning/slots`
- `PATCH /api/v1/planning/slots/{slot_id}` avec verrouillage optimiste
- `POST /api/v1/planning/slots/{slot_id}/cancel`

ERP :

- `POST /api/v1/sites/{site_id}/erp-imports`
- prévisualisation et confirmation avant matérialisation.

## 12. Fiabilité et sécurité

- La source authentifiée détermine le site ; le client ne choisit pas librement `site_id` dans un événement.
- Le secret de passerelle est stocké haché, affiché une seule fois et rotatif.
- La passerelle conserve une outbox locale jusqu'à acquittement.
- Le backend acquitte uniquement après commit.
- Même `event_id` et même payload : doublon accepté sans nouvel effet.
- Même `event_id` et payload différent : conflit et alerte.
- Les événements hors ordre restent acceptés grâce à leur horodatage source.
- Toute correction de mapping, planning ou ERP après matérialisation est auditée.
- Les droits restent séparés : lecture, import ERP, supervision/configuration et administration.

## 13. Critères d'acceptation MVP

1. Créer un site sans ERP puis ouvrir immédiatement son Atelier.
2. Ajouter plusieurs presses depuis l'Atelier sans passer par Imports.
3. Créer une source de site, recevoir un secret et détecter plusieurs identifiants de presses.
4. Mapper ces identifiants et rejouer sans perte les événements reçus avant mapping.
5. Planifier le même OF sur plusieurs presses pendant la même période.
6. Recevoir deux flux portant ce même OF et obtenir deux lignes de suivi indépendantes.
7. Afficher les cycles et paramètres, sans inventer de pièces bonnes ou de rebuts.
8. Importer ensuite une ligne ERP par presse et enrichir la bonne ligne du planning.
9. Additionner les quantités ERP courantes au niveau de l'OF sans les doubler lors d'un réimport.
10. Garantir l'isolation entre deux sites portant les mêmes références OF ou presse.
