# Matrice de préparation — pas une validation jury

Consultation le 9 septembre 2026. Références : **R** = `[Dev IA - titre 2023] Referentiel Activites Compétences et évaluation`, extrait `03.txt` ; **G** = `Grille individuelle d'évaluation`, extrait `06.txt`, RNCP37827. Originaux identifiés par `manifest.json` du dossier temporaire `iddrv-certification-audit-6v4cr2h2`. Pages ci-dessous = pagination imprimée. Reformulation des sous-critères, pas remplacement du référentiel. Le présent lot couvre seulement C1–C7 et C14–C16.

Statuts : **Prouvé périmètre** = résultat exécuté, uniquement dans le périmètre précisé ; **Présent non vérifié** = source identifiée sans recette complète ; **Incomplet** = couverture partielle/proposition ; **Absent** = preuve non établie dans le périmètre inspecté, pas affirmation d'absence universelle. Une compétence n'est jamais acquise par présence d'un fichier.

| Sous-critère / source | Statut et pièce | Critère de fin / tâche humaine |
|---|---|---|
| C1 contexte : acteurs, objectifs, environnements, contraintes, budget, organisation, planning (R1, G2) | Incomplet — README existant, présent lot | Commanditaire confirme contexte, budget et responsabilités dans rapport individuel |
| C1 spécifications : outils, services, langages, accès/disponibilité (R1–2, G2) | Incomplet — data-evidence.md | Inventorier chaque source et ses contraintes réelles |
| C1 périmètre extraction et agrégation complet (R1–2, G2) | Incomplet — deux sources synthétiques | Contrat couvrant toutes sources visées |
| C1 récupération effective ; lancement, connexions, erreurs, fin/sauvegarde (R2, G2) | Prouvé périmètre — data_demo.py, 5 tests, CSV/JSON/SQLite seulement | Rejouer sources externes et archiver compteurs attendus/obtenus, erreurs et empreintes |
| C1 versionnement accessible (R2, G2–3) | Incomplet — patch local non publié | Intégration revue ; disponibilité distante à vérifier par responsable, aucun push ici |
| C1 mix REST/fichier/scraping/DB/big data (R2, G3) | Incomplet — fichiers/DB locale ; scraping/big data absents | Sources autorisées et extractions reproductibles de chaque type ; ne pas renommer fixture en big data |
| C2 SQL fonctionnel SGBD/big data (R2–3, G3) | Prouvé périmètre SQLite ; incomplet global | Exécuter PostgreSQL et système big data dédié, comparer résultats attendus |
| C2 documentation sélections/filtres/conditions/jointures (R3, G3) | Prouvé périmètre — data-evidence.md + QUERY | Étendre aux requêtes réellement utilisées en collecte |
| C2 optimisations explicitées (R3, G3) | Prouvé périmètre — plan SQLite, sans gain revendiqué | EXPLAIN et mesures répétées sur volumes représentatifs isolés |
| C3 agrégation/nettoyage/normalisation unique (R3, G3) | Prouvé périmètre — 5 lignes synthétiques, 3 importées | Vérifier jeux multi-sources réels autorisés, unités/dates et conflits |
| C3 script versionné accessible (R3, G3) | Incomplet — patch local | Revue et intégration puis accès dépôt contrôlé |
| C3 documentation dépendances/commandes/algorithme/choix (R3, G3–4) | Prouvé périmètre — data-evidence.md | Maintenir documentation avec extension des sources |
| C4 modèles conceptuel/physique Merise (R4, G4) | Incomplet — governance-proposal.md ; figures locales non intégrées | Faire relire MCD/MLD complet et correspondance migrations |
| C4 MPD créé sans erreur (R4, G4) | Présent non vérifié — db/init.sql et migrations | Installation PostgreSQL/Timescale à blanc isolée sans erreur |
| C4 choix SGBD motivé (R4, G4) | Incomplet — projection distincte du SGBD projet | ADR charge relationnelle/temporelle, limites et coûts mesurés |
| C4 reproduction installation DB/API (R4, G4) | Présent non vérifié — compose, backend | Recette propre sans services partagés ni fixtures de session |
| C4 import fonctionnel (R4, G4) | Prouvé périmètre — SQLite seulement | Vrai import projet confirmé, persistance et relecture contrôlées |
| C4 documentation import même dépôt, dépendances et commandes (R4–5, G4–5) | Incomplet — data-evidence.md dans même dépôt, pas racine | Clarifier exigence de placement racine avec responsable ; README racine hors périmètre |
| C4 registre tous traitements (R5, G5) | Incomplet — governance-proposal.md | Responsable de traitement complète et approuve inventaire exhaustif |
| C4 procédures tri ; traitements et fréquences (R5, G5) | Incomplet — proposition explicite | Durées/fréquences validées puis exercice synthétique, copies et restauration incluses |
| C5 documentation tous endpoints REST (R5, G5) | Présent non vérifié — backend/app/main.py et routes | Export OpenAPI runtime, rapprochement exhaustif routes/specs |
| C5 documentation authentification/autorisation et standard (R5, G5) | Présent non vérifié — security.py, schémas | Vérifier security schemes et restrictions pour chaque route |
| C5 accès restreint fonctionnel (R6, G5) | Incomplet — anciennes preuves avec session simulée | Login réel, expiration/révocation persistée, 401/403/404 intersites en isolation |
| C5 récupération complète prévue (R6, G5) | Incomplet — Site validé sans HTTP | Relecture réelle après import, champs/compteurs/pagination comparés au contrat |
| C6 thématique outil/réglementation mobilisée (R6–7, G6) | Incomplet — benchmark-watch.md | Valider thème dérive/persistance/confidentialité avec équipe |
| C6 récurrence au moins 1h/semaine (R7, G6) | Incomplet — proposition corrigée à 1h | Calendrier accepté et séances réellement tenues, sans rétrodatation |
| C6 agrégateur cohérent sources/budget (R7, G6) | Incomplet — proposition RSS/Markdown | Configurer flux sélectionnés et budget validé |
| C6 synthèses communiquées accessibles (R7, G6) | Absent — aucun partage réalisé ici | Support accessible, destinataires, date et retours réels |
| C6 informations pertinentes (R7, G6) | Incomplet — benchmark-watch.md | Synthèse recoupée conduisant à décision projet |
| C6 fiabilité auteur/compétence/intérêts, actualité, structure, accessibilité, recoupement (R7–8, G7) | Incomplet — sources locales, fetch externe échoué | Qualifier chacun des axes, ne pas supposer neutralité ni accessibilité d'un éditeur |
| C7 besoin objectifs/contraintes reformulés (R8, G7) | Incomplet — benchmark-watch.md | Commanditaire approuve besoins et seuils |
| C7 services étudiés/non étudiés ; exclusions motivées (R8, G7) | Incomplet — benchmark documentaire limité | Consulter alternatives primaires puis comparer réellement |
| C7 adéquation par ensemble fonctionnel (R8, G8) | Incomplet — tableau de capacités non mesurées | Essais dérive, intégration, exploitation sur même protocole |
| C7 écoresponsabilité selon informations disponibles (R8, G8) | Incomplet — inconnue, pas de score inventé | Sources fournisseur et mesures énergie/ressources contextualisées |
| C7 contraintes/prérequis ; conclusions avantages/limites (R8–9, G8) | Incomplet — benchmark-watch.md | Décision argumentée après accès et essais comparables |
| C14 modèle données formalisé (R16, G15) | Incomplet — proposition entités/cardinalités | Relecture métier et mapping physique complet |
| C14 parcours formalisés (R16, G15) | Incomplet — acceptance-plan.md | Valider schéma avec utilisateurs et scénarios alternatifs |
| C14 contexte/scénarios/validation de chaque spec (R16, G15) | Incomplet — histoires proposées | Couvrir toutes fonctions et critères mesurables validés |
| C14 objectifs accessibilité dans acceptation ; standard cité (R17, G15) | Incomplet — objectifs WCAG 2.2 proposés | Recette clavier/lecteur d'écran/contrastes et écarts tracés |
| C15 architecture/dépendances/runtime (R17, G15) | Présent non vérifié — compose, requirements, frontend/package.json | Versionner diagramme complet et reproduire environnement |
| C15 prestataires écoresponsables favorisés (R17, G16) | Incomplet — données non disponibles | Comparer justificatifs et mesures, choix arbitré |
| C15 diagramme flux (R17, G16) | Incomplet — governance-proposal.md | Compléter flux journaux/fichiers/modèles et frontières de confiance |
| C15 POC accessible/fonctionnelle préproduction (R17, G16) | Présent non vérifié — configuration intégration | Exécution isolée réelle, URL locale et rapport horodaté |
| C15 conclusion précise de poursuite (R17, G16) | Incomplet — recommandation conditionnelle | Décision humaine après résultats POC, critères go/no-go |
| C16 cycles/étapes/rôles/rituels/outils respectés (R18, G16) | Absent — aucune observation collective établie ici | Produire traces contemporaines de réalisation, pas calendrier fictif |
| C16 outils pilotage disponibles (R18, G16) | Incomplet — backlog proposé ci-dessous | Tableau partagé accessible, responsables et état réels |
| C16 modalités/objectifs rituels partagés (R18, G16) | Absent | Invitation/support/retour datés réellement partagés |
| C16 pilotage accessible tout au long projet (R18, G16–17) | Absent | Historique consultable et contrôle d'accès utilisateurs concernés |

## Backlog proposé, sans affectation ni réunion inventée

1. Responsable données à désigner : obtenir sources externes autorisées (C1/C2), finir quand extraction et compteurs sont reproductibles.
2. Référent backend à désigner : installation/import/login/read isolés (C4/C5), finir avec rapport sans mocks ni skips.
3. Responsable de traitement à identifier : compléter registre/conservation (C4), finir avec décisions explicites et exercice approuvé.
4. Candidat + tuteur à solliciter : comparaison et veille ≥1h/semaine (C6/C7), finir avec sources vérifiées et partage réel.
5. Commanditaire/utilisateurs à solliciter : accepter stories, accessibilité, POC (C14/C15), finir avec écarts et décision motivée.
6. Équipe à identifier : conduite agile (C16), finir avec pratiques observées, supports et retours ; aucun historique reconstruit.
