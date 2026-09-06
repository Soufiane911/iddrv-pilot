# Atelier et planning OF multi-presse — Plan d'implémentation

**Spécification :** `docs/superpowers/specs/2026-09-06-atelier-planning-of-design.md`  
**Principe de livraison :** tranches verticales testables, sans réécriture globale de l'application.

## Prérequis — intégrer le travail en cours

Le travail Site/Frontend/Backend le plus avancé se trouve actuellement dans `.worktrees/report-alignment` avec de nombreux fichiers non commités. Ne pas démarrer une implémentation concurrente sur les mêmes fichiers.

Avant la tâche 1 :

- intégrer ou figer le travail de l'autre agent ;
- exécuter ses tests backend, frontend et E2E ;
- relever les contrats réellement disponibles ;
- attribuer le prochain numéro de migration après le dernier fichier intégré ;
- conserver un point de retour Git et une sauvegarde de base.

**Gate P0 :** branche propre, migrations ordonnées, tests de référence enregistrés.

## Tâche 1 — Corriger les invariants bloquants

### Fichiers probables

- `db/init.sql`
- `db/migrations/`
- `db/setup_db.py`
- `ingest/reconciler.py`
- `ingest/ingest_pipeline.py`
- tests data existants

### Travaux

- corriger le décalage paramètres/colonnes dans l'insertion de cycles ;
- supprimer les valeurs métier inventées `good_parts = 1` et `scrap_flag = false` lorsque la source ne fournit pas la qualité ;
- représenter la qualité inconnue par `NULL/unknown` ;
- retirer toute résolution de presse non scellée au site ;
- retirer le défaut silencieux `machines.site_id = 1` ;
- faire exécuter toutes les migrations ordonnées par un même runner pour Docker et le setup local ;
- refuser une migration modifiée après application.

### Vérification

- test DB réel de l'INSERT cycle ;
- cycle sans qualité enregistré avec valeurs inconnues ;
- même référence de presse autorisée sur deux sites sans fuite ;
- création fraîche et upgrade donnent le même schéma.

**Gate P1 :** ingestion fiable et sémantique qualité correcte.

## Tâche 2 — Introduire le modèle OF multi-presse et le planning

### Fichiers probables

- nouvelle migration `db/migrations/02x_workshop_sources_and_planning.sql`
- `backend/app/schemas.py` ou nouveaux schémas ciblés
- nouveau `backend/app/planning_repository.py`
- tests migrations et repositories

### Tables à créer

- `work_orders`
- `work_order_machine_allocations`
- `production_schedule_slots`
- `erp_allocation_snapshots`

### Contraintes

- `work_orders`: unicité du numéro OF normalisé dans un site ;
- `work_order_machine_allocations`: unicité OF-presse ;
- plusieurs affectations autorisées pour le même OF sur différentes presses ;
- plusieurs créneaux autorisés pour une affectation ;
- fin strictement après début ;
- numéro OF stocké comme texte, zéros initiaux conservés ;
- quantités ERP nullables et absentes du formulaire manuel.

### Migration des données

- créer un OF nouveau modèle pour chaque OF historique ;
- déduire le site depuis la presse historique ;
- créer l'affectation et le créneau historiques ;
- copier les valeurs ERP vers un snapshot initial ;
- conserver temporairement les colonnes legacy et prévoir une double lecture contrôlée.

### Vérification

- un OF sur trois presses simultanées ;
- mêmes numéros OF dans deux sites ;
- backfill sans perte ni FK orpheline ;
- réimport snapshot sans double comptage.

**Gate P2 :** modèle multi-presse utilisable indépendamment de l'UI.

## Tâche 3 — Déplacer la création du parc dans l'Atelier

### Backend

Adapter après intégration :

- `backend/app/api/site_management.py`
- `backend/app/api/machine_management.py`
- `backend/app/site_repository.py`
- routes dans `backend/app/main.py`

Règles :

- création Site avec nom et fuseau uniquement ;
- création Presse avec nom et code atelier obligatoires ;
- référence ERP presse facultative ;
- unicités scellées au site ;
- archivage au lieu de suppression dès qu'un historique existe ;
- RBAC : supervisor/admin en écriture.

### Frontend

Adapter :

- `frontend/src/pages/SitesPage.tsx`
- `frontend/src/pages/WorkshopPage.tsx`
- `frontend/src/components/WorkshopWorkspace.tsx`
- nouveaux composants sous `frontend/src/components/workshop/`
- client `frontend/src/lib/api.ts`

Créer :

- `SiteSetupChecklist` ;
- `PressCatalogTable` ;
- `PressFormDrawer` ;
- empty states avec `Ajouter une presse`, `Configurer la passerelle`, `Importer l'ERP`.

Retirer l'import ERP du formulaire initial de création du site. Imports reste un journal et un parcours d'enrichissement, pas le point principal pour créer le parc.

### Vérification

- tests API 201/403/409/422 ;
- tests composants loading/empty/error ;
- E2E site sans ERP puis ajout de deux presses ;
- navigation clavier et conservation de la saisie après erreur.

**Gate P3 :** un atelier vide peut être entièrement préparé sans ERP.

## Tâche 4 — Créer la source de site et le mapping des presses

### Backend et données

Créer :

- `ingestion_sources`
- `source_credentials`
- `source_machine_mappings`
- `cycle_event_receipts`

Ajouter les modules :

- `backend/app/api/site_sources.py`
- `backend/app/source_repository.py`
- `backend/app/api/cycle_ingestion.py`
- service de matérialisation/reprise des événements.

Refactorer le modèle actuel de `machine_connections.py`, qui configure une URL par presse, vers une source au niveau site. Préserver un adaptateur de lecture legacy derrière un feature flag pendant la migration si nécessaire.

Contrat initial :

```http
POST /api/v1/ingestion/cycle-events
Authorization: Bearer <secret-source>
```

Résultats :

- `201` nouvel événement matérialisé ;
- `200` doublon strict ;
- `202` événement conservé mais non mappé/non rapproché ;
- `409` réutilisation du même identifiant avec un autre payload ;
- `422` contrat invalide.

### Frontend

Créer :

- `GatewayCard` ;
- `GatewayCredentialDialog` ;
- `DetectedPressMappingTable` ;
- onglet ou vue `À rapprocher`.

### Vérification

- secret affiché une seule fois, rotation et révocation ;
- plusieurs identifiants externes reçus par une même source ;
- événement avant mapping conservé puis rejoué ;
- retries concurrents sans doublon ;
- source d'un site incapable d'écrire dans un autre ;
- source silencieuse distincte d'une presse arrêtée.

**Gate P4 :** une passerelle locale alimente plusieurs presses sans perte.

## Tâche 5 — Exposer l'API de planning hebdomadaire

### Fichiers probables

- nouveau `backend/app/api/production_planning.py`
- `backend/app/planning_repository.py`
- schémas Pydantic dédiés
- `backend/app/main.py`
- tests API et repository

### Endpoints

- `GET /api/v1/sites/{site_id}/planning?week_start=YYYY-MM-DD`
- `POST /api/v1/sites/{site_id}/work-orders`
- `POST /api/v1/work-orders/{order_id}/allocations`
- `POST /api/v1/planning/slots`
- `PATCH /api/v1/planning/slots/{slot_id}` avec `row_version`/`If-Match`
- `POST /api/v1/planning/slots/{slot_id}/cancel`
- endpoint transactionnel pour créer un OF sur plusieurs presses en une requête.

### Règles

- semaine calculée dans le fuseau du site, puis requêtée en UTC ;
- même OF sur plusieurs presses autorisé ;
- chevauchement de deux OF différents sur une même presse refusé dans le MVP ; une dérogation auditée pourra être étudiée plus tard si le métier en démontre le besoin ;
- modification concurrente renvoie `409` ;
- modification après réception de cycles exige une raison ;
- réponse de grille déjà agrégée pour éviter une requête frontend par cellule.

### Vérification

- Europe/Paris avec changement d'heure ;
- multi-presse simultané ;
- rollback complet d'une création multi-presse partiellement invalide ;
- conflit de version ;
- aucune quantité manuelle inventée.

**Gate P5 :** le planning est cohérent et performant sans frontend.

## Tâche 6 — Construire la grille type Excel

### Fichiers probables

- nouvelle page `frontend/src/pages/ProductionPlanningPage.tsx`
- `frontend/src/App.tsx` pour la route
- composants sous `frontend/src/components/planning/`
- `frontend/src/lib/api.ts`
- styles ciblés et tests Vitest

### Composants

- `ProductionWeekToolbar`
- `ProductionPlanningGrid`
- `ProductionAssignmentEditor`
- `LiveCycleSummaryCell`
- `ProcessParametersPanel`
- `ErpPerPressStatus`

### Première tranche

- route semaine ;
- table sémantique avec en-têtes collants et défilement horizontal ;
- filtres Presse/OF/états ;
- création d'un OF et de plusieurs lignes presse ;
- édition via panneau latéral ;
- états loading/empty/error/stale ;
- lecture seule selon le rôle.

Ne pas ajouter immédiatement une bibliothèque de tableur lourde. Mesurer d'abord le nombre réel de lignes. Ajouter virtualisation seulement si la grille ne tient pas les objectifs de fluidité.

### Vérification

- tests de rendu et de validation ;
- navigation complète au clavier ;
- zéros initiaux du numéro OF préservés ;
- même OF visible sur plusieurs lignes ;
- anciennes valeurs conservées pendant un rafraîchissement échoué.

**Gate P6 :** la planification multi-presse est utilisable de bout en bout.

## Tâche 7 — Relier le direct machine au planning

### Travaux

- matérialiser les événements dans `machine_cycles` après mapping ;
- rapprocher exactement par source/site, presse et OF transmis ;
- associer au créneau par horodatage lorsque possible ;
- conserver l'OF brut transmis ;
- reprendre automatiquement les événements lors de la création d'un OF, d'une affectation ou d'un mapping ;
- exposer compte de cycles, premier/dernier cycle, compteur et paramètres process ;
- rafraîchir la page visible toutes les 2 à 5 secondes ;
- conserver les agrégats séparés des données brutes.

### Cas à couvrir

- OF connu et presse planifiée ;
- OF connu sur une presse non planifiée ;
- OF inconnu ;
- OF absent ;
- presse non mappée ;
- compteur remis à zéro ;
- événements hors ordre ;
- source interrompue.

### Vérification

- aucun cycle perdu ou dupliqué ;
- latence locale observée et enregistrée ;
- nombre de cycles jamais présenté comme nombre de pièces ;
- aucun bon/rebut calculé depuis les paramètres machine.

**Gate P7 :** la grille montre le direct avec une sémantique correcte.

## Tâche 8 — Adapter l'import ERP aux lignes OF-presse

### Fichiers probables

- `backend/app/api/erp_imports.py`
- `backend/app/erp_import_repository.py`
- `ingest/erp_reader.py`
- `ingest/erp_import_jobs.py`
- `frontend/src/components/imports/ErpImportWizard.tsx`
- tests ERP existants et nouveaux E2E

### Travaux

- prévisualiser la clé `site + OF + presse` ;
- faire correspondre la référence ERP presse à une presse du site ;
- enrichir l'affectation existante ou proposer sa création ;
- conserver une version immuable par import ;
- rejeter ou faire arbitrer les doublons OF-presse d'un même snapshot ;
- additionner les quantités courantes par presse dans le total OF ;
- reprendre les cycles précédemment non rapprochés ;
- retourner au planning filtré sur les lignes enrichies.

### Vérification

- deux lignes ERP du même OF sur deux presses différentes ;
- quantités propres conservées par presse ;
- total OF égal à leur somme ;
- réimport identique inchangé ;
- correction ultérieure versionnée et non additionnée ;
- presse inconnue et OF non planifié traités avant confirmation.

**Gate P8 :** l'ERP tardif enrichit le direct sans doublon.

## Tâche 9 — Durcissement transversal

### Travaux

- RBAC complet et isolation multi-site ;
- audit des modifications de mapping, planning et déclarations ERP ;
- métriques : événements reçus, doublons, retard, files en attente, erreurs par source ;
- limites de payload et endpoint batch borné ;
- sauvegarde/restauration testée ;
- test de charge local sur ingestion et lecture semaine ;
- documentation de configuration de la passerelle.

### Scénario E2E de recette

1. créer un site sans ERP ;
2. ajouter deux presses ;
3. créer une passerelle et pousser deux identifiants externes ;
4. mapper les presses ;
5. planifier le même OF sur les deux presses ;
6. pousser des cycles avec paramètres différents ;
7. vérifier deux lignes directes et aucune qualité inventée ;
8. importer deux lignes ERP avec quantités propres ;
9. vérifier le détail par presse et le total OF ;
10. rejouer événements et fichier, puis vérifier l'idempotence ;
11. répéter les mêmes références dans un second site et vérifier l'isolation.

**Gate final :** tests backend, migrations, frontend, E2E, accessibilité et restauration verts.

## Ordre de livraison recommandé

1. **Lot A — Atelier autonome :** tâches 1, 3 et fondation de 4.
2. **Lot B — Planification statique :** tâches 2, 5 et 6.
3. **Lot C — Suivi direct :** fin de 4 puis tâche 7.
4. **Lot D — Confirmation ERP :** tâche 8.
5. **Lot E — Qualification pilote :** tâche 9.

Le frontend et le backend peuvent avancer en parallèle après gel des contrats, avec mocks OpenAPI, mais un seul responsable doit modifier `frontend/src/lib/api.ts`, `backend/app/schemas.py`, `backend/app/main.py` et les migrations partagées pendant chaque vague.
