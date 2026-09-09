# Modélisation C4 — Merise textuel et ancrage physique

Référence inspectée : `59a4846b` (iddrv-pilot), `db/init.sql` + migrations **001 à 025**, et `db/setup_db.py`. Ce document ne prétend pas que ces migrations ont été appliquées sur une base utilisateur : aucune connexion réalisée. [Index des 59 tables déclarées et empreintes](sql-source-index.json). La lecture du SQL complet fait autorité sur ces vues simplifiées.

Les propositions locales `Preuve-manquante/architecture/02_mcd_atelier_hdt.mmd`, `03_mld_atelier_hdt.mmd`, `04_schema_physique_reference.md` et `05_conservation_purge_proposee.md` ont servi de point de départ (lecture seule, non dépendance d'exécution). Complément à [governance-proposal](../governance-proposal.md). Aucun faux objet `uploads`, `audit_logs` ou `operators` n'est ajouté au MPD.

## MCD : entités, associations, cardinalités Merise

Notation : `ENTITÉ (#identifiant ; propriétés)` ; `A (min,max) — association — (min,max) B`. La cardinalité près de A compte les participations d'une occurrence de A. `n` = plusieurs ; `#` identifiant conceptuel, pas nécessairement une PK SQL. Les sous-vues suivantes modélisent le noyau et les traitements RGPD ; le catalogue annexe couvre les tables périphériques, pas un MCD exhaustif de tous leurs attributs.

Entités : SITE (#site ; nom, fuseau, état), MACHINE (#machine ; code atelier, référence ERP facultative, état), COMPTE (#compte ; email, nom affiché, actif), SESSION_AUTH (#session ; expiration, révocation), DOSSIER_IMPORT (#dossier ; nom, état), FICHIER_IMPORT (#fichier ; nom, profil), DÉCISION_MAPPING (#décision ; colonne, décision), OF_ERP (#site+#référence ; opérateur éventuel, période), ÉQUIPE (#équipe ; période, opérateur éventuel), INCIDENT (#incident ; symptôme, période), DIAGNOSTIC (#diagnostic ; résultat), FEEDBACK (#feedback ; verdict, commentaire), PROPOSITION (#proposition ; action), DÉCISION_ACTION (#décision ; motif, date), PASSEPORT (#passeport ; provenance), OF_ATELIER (#ordre ; numéro, note), AFFECTATION (#affectation), CRÉNEAU (#créneau ; période, note).

```text
SITE (0,n) — possède — (1,1) MACHINE
COMPTE (0,n) — HABILITER [rôle,date] — (0,n) SITE
COMPTE (0,n) — ouvre — (1,1) SESSION_AUTH
SITE (0,n) — contient — (1,1) DOSSIER_IMPORT
COMPTE (0,n) — crée — (0,1) DOSSIER_IMPORT
DOSSIER_IMPORT (0,n) — contient — (1,1) FICHIER_IMPORT
DOSSIER_IMPORT (0,n) — justifie — (1,1) DÉCISION_MAPPING
FICHIER_IMPORT (0,n) — concerne — (0,1) DÉCISION_MAPPING
COMPTE (0,n) — décide — (0,1) DÉCISION_MAPPING
SITE (0,n) — identifie — (1,1) OF_ERP
MACHINE (0,n) — porte — (0,1) OF_ERP
MACHINE (0,n) — accueille — (1,1) ÉQUIPE
OF_ERP (0,n) — rattache — (0,1) ÉQUIPE
SITE (0,n) — reçoit — (1,1) PASSEPORT
MACHINE (0,n) — signale — (1,1) INCIDENT
INCIDENT (0,n) — investigue — (1,1) DIAGNOSTIC
INCIDENT (0,n) — reçoit — (1,1) FEEDBACK
DIAGNOSTIC (0,n) — reçoit — (0,1) FEEDBACK
INCIDENT (0,n) — suggère — (1,1) PROPOSITION
PROPOSITION (0,1) — statue — (1,1) DÉCISION_ACTION
COMPTE (0,n) — statue — (1,1) DÉCISION_ACTION
SITE (0,n) — planifie — (1,1) OF_ATELIER
OF_ATELIER (0,n) — répartit — (1,1) AFFECTATION
MACHINE (0,n) — reçoit — (1,1) AFFECTATION
AFFECTATION (0,n) — réserve — (1,1) CRÉNEAU
```

HABILITER porte une seule valeur de rôle par couple compte/site. Un identifiant opérateur ERP n'est **pas** une relation FK vers COMPTE. FEEDBACK n'a **pas** d'auteur structuré dans SQL 003 ; le texte peut identifier une personne. Les acteurs texte du planning ne sont pas des FK utilisateur. Aucune déduction « personne absente » à partir de l'absence de FK.

Extension analytique conceptuelle : MACHINE (0,n) — émet — (1,1) ÉVÉNEMENT_PULL ; une CONNEXION appartient à une MACHINE (1,1), et une MACHINE possède (0,1) CONNEXION. ÉVÉNEMENT_PULL (0,n) — déclenche — (1,1) TRAVAIL_HDT ; TRAVAIL_HDT (0,1) — produit — (1,1) PRÉDICTION. DÉCLARATION_ERP (0,n) — historise — (1,1) RÉVISION ; la révision courante est facultative. Le CYCLE est une observation temporelle, sans inventer une PK globale absente du SQL.

## MLD : relations clés (attributs métier au dictionnaire)

Notation `PK(...)`, `FK(colonnes)->relation(clé)`, `?` nullable ; colonnes omises ici à consulter dans SQL. Chaque relation ci-dessous existe réellement.

```text
sites PK(id)
machines PK(id), site_id NOT NULL FK->sites(id), UQ(site_id,workshop_code), UQ(site_id,erp_ref?)
users PK(id), UQ(lower(email))
user_site_roles PK(user_id,site_id), FK user_id->users, FK site_id->sites, role
sessions PK(id), user_id NOT NULL FK->users, UQ(token_hash)
import_sessions PK(id), site_id NOT NULL FK->sites, created_by? FK->users
import_session_files PK(id), session_id NOT NULL FK->import_sessions
semantic_mapping_decisions PK(id), session_id NOT NULL FK->import_sessions, file_id? FK->import_session_files, decided_by? FK->users
production_orders PK(site_id,id), FK(site_id,machine_id?)->machines(site_id,id)
shifts PK(id), machine_id NOT NULL FK->machines, FK(order_site_id?,production_order_id?)->production_orders(site_id,id)
import_passports PK(id), site_id NOT NULL FK->sites
incidents PK(id), FK(site_id,machine_id)->machines(site_id,id)
diagnostic_runs PK(id), incident_id NOT NULL FK->incidents
feedback PK(id), incident_id NOT NULL FK->incidents, run_id? FK->diagnostic_runs
action_proposals PK(id), incident_id NOT NULL FK->incidents, run_id? FK->diagnostic_runs
action_proposal_decisions PK(id), proposal_id NOT NULL UNIQUE FK->action_proposals, decided_by NOT NULL FK->users
work_orders PK(id), UQ(site_id,id), UQ(site_id,order_number_normalized)
work_order_allocations PK(id), FK(site_id,work_order_id)->work_orders(site_id,id), FK(site_id,machine_id)->machines(site_id,id)
planning_slots PK(id), FK(site_id,allocation_id,machine_id)->work_order_allocations(site_id,id,machine_id)
planning_audit_events PK(id), site_id NOT NULL FK->sites, actor_id? TEXT, entity_id UUID (pas FK polymorphe)
```

Attention : SQL 005 n'impose pas par FK composite la cohérence entre `semantic_mapping_decisions.session_id` et le dossier du `file_id`. Le simulateur protège les **deux** références. SQL 003 ne garantit pas à lui seul que `feedback.run_id` appartient à son `incident_id` ; l'autorisation/contexte applicatif doit être vérifié séparément. Ne pas qualifier toutes les relations d'isolées par le seul dessin.

## MPD textuel : autorité et contraintes réelles

```text
init.sql -> seed_data.sql -> migrations 001..022 (ordre lexical, checksum setup)
  PostgreSQL : PK, FK composites, UNIQUE, CHECK, UUID, JSONB, TIMESTAMPTZ
  TimescaleDB : machine_cycles(time) -> chunks 7 jours
    UQ partielle(time,machine_id,source_row_hash) ; pas PK globale déclarée
    FK(source_event_id,machine_id,time) -> machine_source_events(id,machine_id,cycle_ended_at) [015]
    FK(cycle_event_receipt_id,time) -> cycle_event_receipts(id,occurred_at) CASCADE [021]
    -> machine_cycles_hourly (vue continue, pas table utilisateur)
  016/019 : triggers histoire hdt_predictions, cycle_context_links
  022 : DELETE sites et machines bloqué ; archivage non destructif
```

[init.sql](../../../db/init.sql), [setup](../../../db/setup_db.py), [migrations](../../../db/migrations). Le MPD **effectif** exige exécution sur PostgreSQL/Timescale propre et comparaison du catalogue : cet exercice SQLite ne la remplace pas. Le contrôle de 24 empreintes sources détecte une dérive documentaire, pas la réussite du DDL.

Choix PostgreSQL/Timescale : relations nombreuses, transactions, intégrité multi-site et révisions, JSONB pour provenance hétérogène ; séries temporelles volumineuses indexées par machine/temps et agrégats. SQLite seul ne reproduit ni Timescale, ni PL/pgSQL, ni exclusion GiST du planning. Un stockage documentaire seul déplacerait la cohérence des références dans l'application. Compression après 30 jours = optimisation, **aucune durée RGPD**. `[début,fin)` des créneaux non annulés évite chevauchement ; l'identité OF atelier est distincte de l'OF ERP.

## Dictionnaire ciblé des données et provenance

Types et cardinalités détaillées dans les relations ci-dessus ; `*` ci-dessous désigne une famille d'attributs, non un nom de colonne SQL.

| Relations / attributs | Type / sens / qualification | Autorité SQL |
|---|---|---|
| users.email, display_name, password_hash, is_active | VARCHAR(320), VARCHAR(150), TEXT, BOOL ; identité et secret dérivé personnel | 004:48 |
| user_site_roles.user_id, site_id, role | UUID, INT, VARCHAR(20) ; habilitation par couple, viewer/analyst/supervisor/admin | 004:60 |
| sessions.user_id, token_hash, expires_at, revoked_at, last_seen_at | UUID, VARCHAR(128), TIMESTAMPTZ ; session **globale compte**, pas site_id | 004:68 |
| sites.name, timezone, status ; machines.workshop_code, erp_ref | identité industrielle ; références/fuseau/état, ERP nullable ; recoupement possible, pas personnel par nature | init:15/28, 022 |
| production_orders.operator_id ; shifts.operator_id | VARCHAR(50), nullable ; identifiant opérateur non FK personne | init:56/79, 006/010 |
| operator_notes.operator_id, note_text | VARCHAR(80), TEXT obligatoire ; données personnelles possibles, texte à minimiser | 002:20, 009/010 |
| quality_checks.comment ; maintenance_events.description | TEXT ; commentaires pouvant contenir noms ou appréciations | 002:2/14, 009 |
| import_passports.file_name, file_path_raw, error_log, metadata | VARCHAR/TEXT/JSONB ; provenance, chemin, contenu libre ; site obligatoire | init:93, 007/022 |
| staging_import_rows.raw_data, normalized_data ; import_rejections.raw_value, message | JSONB/TEXT ; copie potentielle des données personnelles source | init:115/130 |
| evidence_vault.context_json ; data_quality_issues.raw_value, description | JSONB/TEXT ; contexte/preuves et anomalies, liens passeport facultatifs | init:143/159 |
| import_jobs.*path, last_error, metadata ; import_job_events.detail | TEXT/JSONB ; chemins et diagnostics, copies archive/quarantaine | 004:123/149, 007 |
| import_sessions.created_by, name, summary ; import_session_files.file_name, profile | UUID FK nullable, VARCHAR, JSONB ; auteur/profil de fichiers | 005:2/14 |
| semantic_mapping_decisions.decided_by, source_column, canonical_field | UUID FK nullable, VARCHAR ; décision et auteur, fichiers optionnels | 005:29 |
| erp_import_requests.creator_id, raw_path, original_name, preview, choices, result | UUID FK obligatoire, TEXT, JSONB ; upload et aperçu persistant | 013:72 |
| site_shift_calendars.author_id ; erp_declaration_revisions.raw_data ; production_order_revisions.values | UUID FK, JSONB ; auteur/calendrier et copies historisées | 013:11/30/60, 015 |
| machine_cycles.raw_data ; machine_source_events.payload ; cycle_event_receipts.payload | JSONB ; mesures industrielles, données non canoniques potentiellement identifiantes | init:175, 014:36, 021:62 |
| hdt_scoring_jobs.input_snapshot ; hdt_predictions.input_event_ids, signals ; diagnostic_runs.result, context_snapshot | JSONB ; propagation indirecte d'identifiants et contexte | 014/016, 003 |
| feedback.comment | TEXT nullable, pas colonne auteur ; incident obligatoire, diagnostic facultatif | 003:30, index 012 |
| diagnostic_evidence.excerpt, observation ; diagnostic_hypotheses.missing_data | TEXT/JSONB ; extraits/contextes potentiellement personnels | 003:17/24 |
| action_proposal_decisions.decided_by, reason ; continuity_recovery_reviews.actor_user_id, confirmation | UUID FK non nullable, TEXT ; décisions humaines à préserver en attendant arbitrage | 004:86, 018 |
| work_orders.note, created_by ; work_order_allocations.created_by ; planning_slots.note, created_by | TEXT ; auteur texte sans FK, commentaires libres | 020:8/29/48 |
| planning_audit_events.actor_id, before_state, after_state | TEXT, JSONB ; journal applicatif avec copies avant/après | 020:87 |
| machine_connections.base_url, secret_ref ; site_source_credentials.secret_hash | TEXT ; infrastructure/secrets dérivés, pas systématiquement personnels mais sensibles | 014:3, 021:25 |

Le catalogue JSON donne le chemin exact de chaque numéro de migration et les premières déclarations ; les changements 006/007/009/010/011/013/015/016/017/019/020/021/022 restent indispensables. Compléter le dictionnaire attribut par attribut de toutes les tables pour une défense Merise exhaustive.
