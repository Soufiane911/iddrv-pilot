# Modèles, registre et conservation — propositions à faire valider

9 septembre 2026. Aucune conformité RGPD attestée ; aucun effacement exécuté. Lecture seule des propositions locales `Preuve-manquante/architecture/05_conservation_purge_proposee.md` et de `db/init.sql`. L'inventaire ci-dessous n'est pas exhaustif.

## Modèle conceptuel partiel (notation entité-association Merise textuelle)

SITE (#id, nom, fuseau) — possède — MACHINE (#id, référenceERP, nom).
Cardinalités : SITE (0,n), MACHINE (1,1). Identité métier MACHINE : (site, référenceERP), unicité distincte de l'identifiant technique. MACHINE — porte — ORDRE (#id, début, fin, opérateur) : MACHINE (0,n), ORDRE (0,1), conformément à la FK nullable du schéma initial. Cette cardinalité technique doit être confrontée au besoin. L'identifiant opérateur peut être personnel.

MLD partiel : SITE(id PK, name UNIQUE, timezone) ; MACHINE(id PK, site_id FK SITE NOT NULL, erp_ref, UNIQUE(site_id,erp_ref)) ; PRODUCTION_ORDER(id PK, machine_id FK MACHINE nullable, started_at, ended_at, operator_id). MPD de référence : `db/init.sql` **et toutes migrations** ; SQLite de démonstration n'en est pas la validation. Compléter cycles, imports/révisions, utilisateurs/sessions, incidents/prédictions et règles historiques avant de qualifier le modèle de complet.

Flux partiel proposé : fichiers/API machine → ingest (validation, normalisation, rejets) → PostgreSQL/Timescale (contexte et cycles) → modèles/score → API authentifiée → frontend. Branches à inventorier : raw/archive/quarantaine, journaux, exports, modèles et sauvegardes. Les fichiers et exports ne disparaissent pas par suppression SQL. Relier ces flux à un diagramme complet et aux frontières de confiance avant recette.

## Registre de travail

Pour **chaque ligne**, champs obligatoires à compléter par responsable compétent : responsable de traitement/contact, finalité approuvée, base légale, catégories de personnes et de données, destinataires/sous-traitants, transferts et garanties, durées active/archive et justification, mesures de sécurité, exercice des droits, besoin d'analyse d'impact, propriétaire et date de validation. Aucun fondement légal n'est présumé.

| Famille candidate | Finalité à confirmer | Données/risque à inventorier | Durée et autorité |
|---|---|---|---|
| Comptes, rôles, sessions | Accès et sécurité | email, nom, identifiants, dates de session | Non décidées |
| Imports, rejets, copies brutes | Rejeu et diagnostic ingestion | identifiants opérateurs, chemins et contenu libre | Non décidées |
| Cycles, ERP, contexte | Analyse production | opérateur, horodatages et recoupements possibles | Non décidées |
| Incidents, feedback, audit | Suivi et justification | auteur, commentaires, événements | Non décidées |
| Exports, modèles, jeux d'analyse | Reproductibilité | identifiants et réidentification possible | Non décidées |
| Logs techniques, sauvegardes | Exploitation/restauration | IP ou identifiants éventuels, copies de toutes familles | Non décidées |

## Procédure de tri proposée, non activée

Fréquences **proposées** : inventaire initial puis revue mensuelle des changements ; contrôle hebdomadaire des lots arrivant à échéance **après définition des durées** ; revue des suspensions à chaque demande d'effacement ou incident ; contrôle de non-réintroduction à chaque restauration. Responsable et cadence finale restent à approuver ; aucune ordonnance automatique livrée.

1. Qualifier minimisation et besoin réel champ par champ ; décider durée/déclencheur et exceptions documentées. Séparer conservation active et archivage ; compression Timescale et archivage UI ne sont pas effacement.
2. Produire un aperçu en lecture seule par site, catégories, échéances, compteurs et dépendances FK/triggers. Pas d'export de contenu personnel dans la preuve.
3. Faire approuver le lot concret, copies fichiers et sauvegardes comprises ; examiner obligations de conservation et suspensions avant destruction.
4. Concevoir et tester exclusivement sur copie synthétique : intégrité référentielle, isolation intersites, historique protégé, erreurs, reprise et restauration ; ne désactiver aucun trigger pour contourner une règle.
5. Après autorisation distincte seulement, exécuter outil audité et journaliser version/règle, dates, auteur, compteurs avant/après, erreurs. Vérifier fichiers/exports/sauvegardes et l'absence de réintroduction lors d'une restauration.
6. Fin : rapport d'exercice synthétique, registre et durées approuvés, contrôle des droits et copies. Ce lot ne satisfait pas cette fin ; aucun script destructif fourni.
