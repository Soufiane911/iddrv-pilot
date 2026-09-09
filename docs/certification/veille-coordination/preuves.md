# Exigences et preuves vérifiées

Consultation : 9 septembre 2026. Base Git : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a`. Les références locales originales sont indexées avec SHA-256 dans [index.json](index.json); elles ne sont pas publiées par ce dossier.

## Références et règles

Extraits officiels fournis dans le dossier temporaire `iddrv-certification-audit-6v4cr2h2` : `03.txt` (référentiel RNCP37827), `06.txt` (grille individuelle), `04.txt` (règlement général version 7bis du 24 octobre 2024), `05.txt` (règlement spécifique). Leur `manifest.json` identifie les originaux. Les pages ci-dessous sont imprimées, pas des numéros de fichier PDF.

- C6 : référentiel pages 6–8, lignes 212–275; grille pages 6–7, lignes 234–305. Thème outil/réglementation mobilisé; **planification d'au moins une heure hebdomadaire**; agrégateur cohérent avec sources et budget; synthèse pertinente communiquée dans un format accessible; qualification auteur, compétence, intérêts, actualité, structure, accessibilité et recoupement.
- C16 : référentiel page 18, lignes 655–683; grille pages 16–17, lignes 734–770. Cycles, étapes, rôles, rituels et outils effectivement respectés; pilotage disponible; modalités/objectifs des rituels partagés; supports accessibles à toutes les parties tout au long du projet.
- Règlement spécifique pages 7–8 et 11–13 : rapports professionnels et soutenances individuels E2/E4; démonstration pour E4; évaluation et décision par le jury. Le contexte peut être réel ou fictif, ce qui n'autorise pas à inventer une exécution ou des personnes.
- Règlement général section 7, page 12 : sanctions de fraude et citation des auteurs, y compris des modèles dont on s'inspire. Les synthèses présentes sont originales et assistées par IA; aucun compte rendu humain fabriqué. Les règles d'assistance autorisée à l'épreuve restent à confirmer auprès du responsable de session.
- Recherche de `AGENTS.md` dans le worktree et emplacements parents usuels : aucun fichier trouvé. Skills systems-architect et code-reviewer lus; inspection avant rédaction, puis contrôle documentaire final sans modification du code.

## Preuves effectives, sans extrapolation

### P1 — plan versionné puis intégration

`docs/superpowers/plans/2026-09-06-atelier-planning-of.md`, dernier commit propre à ce fichier `bee8ce0f13cfba9f644a426bf31c234fb3e588d3` daté `2026-09-06T16:53:14+02:00`. Début lu : tranches verticales, gates, interdiction de travail concurrent sur les mêmes fichiers et intégration du travail d'un autre agent. Git montre aussi `c75d7b52bcba07806422419e8079d17ba86d7ea5` puis merge `828426004241b1282765b08671224d9d7018d349`, le 7 septembre. Cela atteste supports et changements versionnés, **pas** réalisation de chaque gate ni rituel humain.

### P2 — cycle public PR → CI → fusion

API GitHub publique consultée en GET sans jeton à `2026-09-09T14:29:31Z` (HTTP 200).

- [PR numéro 1](https://github.com/Soufiane911/iddrv-pilot/pull/1) créée `2026-09-09T13:51:18Z`, fusionnée `2026-09-09T13:59:23Z`, merge SHA égal à la base du présent lot. Objet : catalogue HDT en lecture seule; le corps distingue historique, summary6 et candidats non promus.
- [Relectures de PR](https://api.github.com/repos/Soufiane911/iddrv-pilot/pulls/1/reviews) : tableau vide; zéro commentaire de revue et zéro commentaire général déclarés par la réponse PR. **Aucune approbation humaine de revue établie**. Les cases « avant fusion » du corps restent décochées : ne pas les présenter comme validées.
- [Première page des issues, tous états, maximum 10](https://api.github.com/repos/Soufiane911/iddrv-pilot/issues?state=all&per_page=10) : une seule entrée retournée, la PR numéro 1. Aucun ticket séparé observé dans cette réponse bornée; pas d'affirmation sur d'éventuels outils privés.
- [CI 34359776838](https://github.com/Soufiane911/iddrv-pilot/actions/runs/34359776838), API Actions consultée `2026-09-09T14:30:04Z` : événement `pull_request`, SHA `31c8c2c2a265726c0db513bb25090d982562bb8f`, statut `completed`, conclusion `success`, créée `13:51:22Z`, mise à jour `13:56:23Z`. Preuve d'une conclusion globale sur cette révision, pas audit des logs/jobs ni déploiement/clientvalidation. Le workflow `.github/workflows/ci.yml` est présent; ses premiers jobs lus enchaînent lint, backend, frontend puis smoke Chromium.
- Le corps de PR rapporte 436 tests Python réussis/37 ignorés et 175 frontend/2 ignorés : **déclaration de PR**, pas tests rejoués ici. La CI ne permet pas d'en déduire ces mêmes compteurs.

### P3 — configuration Feedly existante

Lecture seule du README et des quatre captures `Preuve-manquante/organisation/feedly-2026-09-09/`. Trois dossiers visibles; les captures détaillées montrent cinq abonnements chacun. Deux abonnements AWS ne font pas deux éditeurs indépendants. La date du 9 septembre est **déclarée par le README**, pas certifiée par une horloge visible de capture. Les titres d'articles et « Today » ne datent pas la configuration. Les captures attestent l'affichage archivé, ni fonctionnement actuel des flux, ni lecture des articles, ni partage, ni récurrence. Identités et articles non nécessaires ne sont pas reproduits. Aucun accès Feedly effectué.

### P4 — documents locaux antérieurs

`Preuve-manquante/organisation/veille_2026-09-08.md` déclare une lecture ponctuelle CNIL/sklearn et aucun partage; proposait seulement 30 minutes hebdomadaires. Ce seuil est insuffisant au regard de C6. `docs/certification/benchmark-watch.md` au commit `556380d87b5815cbfdf4fe9bfb98b1f0da014efb` corrige déjà la proposition à ≥1 h. Le présent dossier précise un calendrier futur sans modifier les sources antérieures.

`Preuve-manquante/organisation/recette_et_validation.md` : protocole à effectuer; la coordination de préparation y est décrite, explicitement distinguée de l'entreprise. Ce document secondaire ne démontre ni entretien ni recette signée; certains constats techniques datés ne doivent pas remplacer main actuelle.

### P5 — résultats expérimentaux comme entrée de pilotage

Début du rapport local `output/hdt-feature-hypotheses-2026-09-07/REPORT.md` lu (jusqu'à la section livrables), empreinte recalculée, concordante avec `docs/certification/hdt-candidates.md`. Statut `EXPERIMENTAL_NOT_PROMOTED`; 90 événements distincts dans cinq jeux, répétés sur trois graines; plafond FP dépassé sur 61008. Aucune exécution nouvelle ni preuve terrain. Les liens scientifiques de ce rapport, notamment Kistler, n'ont pas été consultés ici. On indexe le rapport, pas les prédictions détaillées ou journaux personnels.

### P6 — session présente

Identifiant technique : `run-mtu7110b-c8d25ad46b51487d`, lot C6/C16. L'instruction reçue du parent déclare une demande utilisateur de coordination parallèle. **La conversation source n'est pas disponible à cet agent** : aucune citation, liste de participants humains, horaire de réunion ou décision utilisateur supplémentaire n'est reconstruite. Seules l'inspection et la rédaction de ce lot sont directement observées. Une répartition utilisateur/orchestrateur/agents n'est pas de la collaboration professionnelle humaine.

## Couverture des sous-critères

| Attendu | Apport constaté | Limite à lever |
|---|---|---|
| C6 thème et pertinence | Dérive, sécurité de persistance, conservation, accessibilité rapprochées du projet | Arbitrage des parties prenantes |
| C6 heure hebdomadaire | Calendrier prospectif écrit | Acceptation et séances réellement tenues |
| C6 agrégation/budget | Captures Feedly et liste versionnée de sources | Coût/licence, accès partagé et flux actuels à confirmer |
| C6 fiabilité | Quatre sources primaires consultées, qualifications explicites | Recoupement indépendant et audits d'accessibilité non établis |
| C6 communication accessible | Support textuel prêt | Envoi, accès destinataires et retours non réalisés |
| C16 cycles et outils | Plan Git, PR/CI/fusion observés | Adoption et continuité de la méthode humaine |
| C16 rituels et partage | Modalités proposées | Invitations, déroulement et retours véritables |
| C16 pilotage accessible | Dossier local versionnable et backlog | Intégration autorisée, partage et accès de toutes les parties |
