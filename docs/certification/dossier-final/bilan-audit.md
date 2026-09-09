# Bilan du dossier sourcé — limites et vérifications

## Périmètre figé

Base : main `59a4846bb13d31c8fb04b1a2dcfa0239c853605a`, fusion de PR #1 catalogue API. Travail documentaire isolé, sans push, déploiement, installation de dépendances, modification de main ni modification des travaux d’autres agents. Aucun fichier `AGENTS.md` trouvé dans ce worktree et ses parents, ni dans la recherche ciblée du projet principal ; la référence historique à AGENTS dans L4 ne prouve pas sa présence actuelle. Skills systems-architect et code-reviewer lus.

Documents officiels S01–S06 et manifest lus à partir des extraits fournis. S02 est un OCR incertain ; S03 et S06 servent aux exigences, S04/S05 aux modalités. Les dix documents préexistants de `docs/certification/` ont été lus. Sélection en lecture seule des pièces `Preuve-manquante/`, sources/cohérence et préparation V6, débuts et synthèses L1–L4, L5 p.1–4. **Pas un audit exhaustif des fichiers output, ni une vérification visuelle de tous les PDF/livrets.** Les extractions des livrets comportent des ligatures altérées.

Les identités et empreintes des pièces sélectionnées sont dans [sources.json](sources.json). Pour une pièce externe, le commit observé désigne le HEAD au moment de lecture, **pas la version productrice**. `unresolved` est intentionnel : ces fichiers ne sont pas distribués et leur disponibilité future/CI n’est pas garantie.

## Livrables

- [Index des critères](index-criteres.md) : 150 clauses adressables, y compris deux groupes et leurs clauses filles ; E1–E5, C1–C21, citations exactes S06 avec pages imprimées, statut et prochaine preuve.
- [Index structuré](index-preuves.json) : mêmes clauses, portée de l’audit, référence complémentaire S03 et liens aux preuves.
- [Inventaire des sources](inventaire-sources.md) et [sources.json](sources.json) : chemins, commit observé, PR/run, commande ou lecture, périmètre/limites et prochaine preuve.
- [Conducteur](conducteur-soutenance.md) : proposition pour cinq épreuves, démonstrations bornées, secours et checklist des modalités avec conflits visibles.

Les 150 entrées ne sont **ni 150 critères indépendants du jury**, ni un score de couverture. C4.08–09 sont les détails de C4.07 et C6.07–12 ceux de C6.06. Les statuts qualifient les preuves, jamais l’acquisition d’une compétence.

## État de préparation par épreuve

| Épreuve | Appuis sélectionnés | Manques et limites déterminants |
|---|---|---|
| E1 | Microdémo P01 réellement rejouée ; schéma/propositions ; anciennes preuves ERP/API bornées | Mix complet de sources non établi sur main ; big data exécuté non établi ; SQL métier historique non exécuté dans la pièce X01 ; Merise/RGPD et recette auth/persistance incomplètes. |
| E2 | Benchmark préparatoire, identité du modèle et catalogue scientifique | Comparaison complète de services, cadence/partage de veille et décision humaine à établir ; catalogue ≠ benchmark suffisant, ni service installé. |
| E3 | Tests/packaging/monitorage historiques et configurations | Recette réelle intégrée, restitution scorer, couverture définie, chaîne modèle exécutée et livraison cible à établir. Recherche ≠ validation industrielle. |
| E4 | Code versionné, fusion/catalogue PR #1 vérifiés Git (revue interne déclarée, non relue ; P09), CI main réussie signalée/corroborée, plans de recette | Coordination historique non démontrée ; accessibilité et acceptation non établies ; Delivery main réellement échouée, correction branche seulement. |
| E5 | Incident E2E corrigé localement et documenté ; supervision synthétique historique ; nouveau cas build Web en branche | Rejeu/archives avant-après et lien outil de suivi à compléter ; alerte reçue en environnement opérationnel non établie. L5 confinement et X03 retour sain ne sont pas des correctifs de code. |

## Évolutions en parallèle : ne pas annoncer « intégré »

| Snapshot stable lu | État documentaire retenu |
|---|---|
| `4b6b458d`, fix/delivery-status-report | P11 : rapport corrigé, défaut build Web reproduit et vrai Docker build local réussi rapportés. Non fusionné, aucun nouveau succès Delivery main revendiqué. |
| `54156891`, feat/certification-data-sources | P12 : snapshot en correction ; HTTP public auxiliaire, projection PostgreSQL et DuckDB rapportés, Spark non exécuté. Ne pas importer ses conclusions comme validation finale de sécurité ni comme collecte industrielle. |
| `ea54dc70`, feat/summary6-replay | P13 : moteur expérimental et paquet privé, tests bornés. API en chantier hors snapshot. Ni main ni livrets modifiés par ce travail. |
| RGPD, accessibilité, veille | Agents en cours, pas de commit stable fourni dans ce lot : **non audité**, aucune couverture ajoutée par anticipation. |

CI `34360646172` success et Delivery `34361237874` failure sont des traces authentiques signalées par le mandat et corroborées par le document versionné P11. **Pas de requête GitHub effectuée ici.** P11 a consulté runs/jobs/annotations ; logs complets refusés 403. Une vraie erreur Docker locale ne prouve pas être l’unique cause distante. L’étape API réussie peut avoir publié une image ; ne pas annoncer « aucune publication ».

## Vérifications réellement effectuées dans ce lot

1. `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_certification_data_demo.py -v` : **5 tests réussis**, zéro ignoré, 0,100 s rapporté. SQLite temporaire, sources synthétiques, contrat Site ; pas de conftest applicatif chargé, ni de stack réseau/DB externe provisionnée.
2. Contrôle JSON par bibliothèque standard : unicité des 150 IDs, couverture des 21 compétences et cinq épreuves, existence des références de preuves et prochaines preuves, concordance des citations JSON/Markdown. Ceci vérifie l’index, **pas l’atteinte des critères**.
3. **31 références de fichiers Git** résolues par `git show <observed_commit>:<path>` et empreintes SHA256 comparées à `sources.json`. Les références externes sont explicitement `unresolved`, jamais exigées comme fichiers locaux de CI.
4. Lecture et contrôle des clauses extraites de S06 p.2–22, avec retours de ligne normalisés ; conservation des coquilles et des sous-listes. Relecture croisée de S03. Aucun recours à l’OCR S02 pour arbitrer une exigence.
5. Contrôle ciblé de l’absence de chemins personnels absolus dans les nouveaux fichiers ; aucun log brut, identité personnelle, token ou payload métier collecté. Ce contrôle textuel ne remplace pas une revue humaine avant partage.
6. `git diff --check` : sans erreur sur le périmètre indexé. Aucun test applicatif complet, test de charge, audit OWASP/WCAG exhaustif, entraînement, build Docker ou déploiement exécuté dans ce lot.

Correction documentaire après revue : P09 distingue fusion/catalogue vérifiés Git, revue interne effective déclarée par le parent non relue, et absence d’approbation publique observée dans le relevé veille API du 2026-09-09T14:29:31Z, sans nouvelle requête ni collecte privée. C4 conserve les citations et sépare les quatre pièces minimales des recommandations opérationnelles facultatives ; une procédure de tri manuelle est possible. Base et snapshots restent figés, sans intégration des autres branches. Vérifications renouvelées après correction : JSON, 150 IDs uniques, 21 compétences, cinq épreuves, références, citations/pages inchangées et prochaines preuves concordantes JSON/Markdown, 31 empreintes Git, sept liens locaux Markdown, cohérence sources/inventaire et `git diff --check`. Aucun test applicatif ni lecture des originaux officiels externes rejoué pour cette correction.

Les résultats historiques P05–P08/P11–P13 restent ceux de leurs auteurs/documents et environnements. Ils ne sont pas additionnés aux cinq tests de ce lot ni réattribués au dernier SHA.

## Absence constatée, non-audit et actions humaines

- **Absence constatée dans la sélection :** preuve de big data réellement exécuté ; déploiement réussi de Delivery main cité ; correction nouvelle de code dans le cas L5/X03 ; confirmation02 indépendante EWM20 dans le catalogue. Il ne s’agit pas d’une affirmation sur tous les fichiers privés ou tous les systèmes.
- **Non audité :** totalité des artefacts output, discussions détaillées de PR, historique complet de tickets/réunions, accessibilité terrain, réception client, environnement de production, travaux d’agents non stabilisés. Ne pas écrire « absent » pour ces sujets.
- **À réaliser par les personnes compétentes :** confirmation des modalités/échéances par responsable de session ; preuve de partage/retours et contribution personnelle par candidat ; acceptation métier/POC par commanditaire ; registre/durées par responsable de traitement ; autorisation des sources et de la stack par exploitant.
- Aucune réunion, séance historique de veille, affectation, identité de client, consentement ou décision n’est reconstruite. Un backlog proposé n’est pas une conduite agile passée.
- S04 p.6 réserve l’acquisition à la validation de tous les critères et au jury souverain ; pas de probabilité arbitraire de réussite.
