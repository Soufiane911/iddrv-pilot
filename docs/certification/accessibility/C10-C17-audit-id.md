# Audit accessibilité C10/C17 — iddrv-pilot

## Périmètre et référentiel

Base Git : `59a4846b`, worktree isolé du workflow. Aucun fichier AGENTS.md trouvé dans le worktree ni ses ancêtres. Skills fullstack-engineer et code-reviewer lus ; revue finale séparée des correctifs. Aucun backend, ML, fichier API, monitoring, WorkshopPage, ProcessDriftPanel, package.json ni test d’un autre agent modifié. Pas de publication.

Extraits exacts lus dans les fichiers de certification fournis, répertoire temporaire `iddrv-certification-audit-6v4cr2h2` :

- `03.txt:399–407` et `06.txt:459–479`, C10 : « Intégrer l’API d’un modèle ou d’un service d’intelligence artificielle dans une application, en respectant les spécifications du projet et les normes d’accessibilité en vigueur, à l’aide de la documentation technique de l’API, afin de créer les fonctionnalités d’intelligence artificielle de l’application. »
- Activité explicite `03.txt:430–433` : « Test et validation, en fonction des enjeux, du niveau d’accessibilité des interfaces modifiées. »
- `03.txt:682–696` et `06.txt:770–780`, C17 : « Développer les composants techniques et les interfaces d’une application en utilisant les outils et langages de programmation adaptés et en respectant les spécifications fonctionnelles et techniques, les standards et normes d’accessibilité, de sécurité et de gestion des données en vigueur dans le but de répondre aux besoins fonctionnels identifiés. »
- Critère C17 : « Les comportements des composants d’interface (validation formulaire, animations, etc.) et la navigation respectent les spécifications fonctionnelles. »
- Activité C17 : « Les enjeux d’accessibilité sont pris en compte lors du développement de l’application, et notamment des interfaces. »

C10 exige aussi communication API, auth/renouvellement, couverture des points de terminaison ; C17 couvre aussi sécurité, accès, métier, documentation. Ce lot apporte uniquement des preuves ciblées d’accessibilité, pas la validation complète de ces compétences.

Référence de travail : [WCAG 2.2](https://www.w3.org/TR/WCAG22/), niveau AA ciblé ; [APG dialog modal](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/). Aucun référentiel légal applicable à l’organisation n’a été déterminé ici, et aucune conformité WCAG/RGAA globale n’est revendiquée.

## Findings avant et correctifs

| Gravité | Avant, risque concret | Après et chemins | Référence |
| --- | --- | --- | --- |
| P1 | Modales sites, presse et planning : Tab sort du dialogue malgré aria-modal. Sites sans Échap/restauration ; effets presse/planning dépendants du callback parent peuvent réinitialiser le focus. | `components/AccessibleDialog.tsx` et CSS : dialog natif en portail, arrière-plan inerte navigateur, focus initial activable, boucle Tab/Maj+Tab, Échap bloqué pendant mutation, restauration si déclencheur encore présent. Adoption dans `pages/SitesPage.tsx`, `components/workshop/PressFormDrawer.tsx`, `components/planning/ProductionAssignmentEditor.tsx`. | 2.1.1, 2.1.2, 2.4.3, 4.1.2 |
| P2 | Erreurs auth et validations métier visibles mais non décrites depuis les champs. | `pages/LoginPage.tsx` : refus décrit par les deux champs sans désigner arbitrairement lequel est invalide. Sites : doublon/nom vide lié et aria-invalid ; presse : nom/code requis, doublons code/ERP ; planning : numéro, dates incohérentes et machines répétées liés à l’erreur. | 1.3.1, 3.3.1, 3.3.2 |
| P2 | Bouton source « Tester la connexion » contourne les contraintes natives du formulaire. | `components/workshop/MachineConnectionPanel.tsx` appelle reportValidity avant mutation. Les opérations sources/auth/sites/presse/planning exposent une annonce d’attente ; archivage annoncé au retour. | 3.3.1, 4.1.3 |
| P2 | Lien d’évitement sans cible focusable ; fermeture menu mobile laisse le focus sur un lien démonté ; échec déconnexion uniquement dans title. | `components/Layout.tsx` : cible main tabindex -1 et focus explicite, restauration bouton Plus sur Échap, erreur de déconnexion role alert. | 2.4.1, 2.4.3, 4.1.3 |
| P2 | Bordures des champs très pâles, seul contour identifiant le champ blanc sur fond blanc. | `styles.css` : bordure champs #E6E8EA → #64748B. Ratio calculé sRGB sur blanc 1,23:1 → 4,76:1 (minimum non textuel 3:1). Focus existant #334155 sur blanc : 10,35:1, outline 3px vérifié dans Chromium. | 1.4.11, 2.4.7 |

Les noms accessibles des champs auth, presse, sources et planning existaient déjà via labels explicites ou englobants et sont conservés. Les statuts ne reposent pas seulement sur la couleur. Le contraste global, les graphiques et les états désactivés n’ont pas fait l’objet d’un inventaire complet.

## Correctif de revue P1/P2 (après `004ade0c`)

- Tests déplacés de `frontend/e2e/` vers `frontend/e2e-accessibility/`, exclus aussi de Vitest. La smoke standard reste en démo/skip-auth ; la suite dédiée les désactive et est exécutée **après** la smoke dans `frontend-e2e`, avec le même Chromium installé, sans secret, port loopback CI dédié `54179`, sans réutilisation de serveur. Les sorties dédiées sont relatives au dépôt (`test-results/accessibility`), sans captures dans un répertoire personnel.
- Suppression des wrappers devenus inertes et de leur CSS inutilisée ; positionnement des drawers conservé par le CSS du dialogue. La fermeture extérieure exige pointer-down, pointer-up puis click hors du rectangle du dialogue, hors mutation. Un glisser commencé à l’intérieur ne ferme pas. Focus initial : premier champ activable, puis bouton en fallback.
- Chromium strict (`CI=true`) : standard **36/36** en **39,8 s**, port `54284` ; dédiée **4/4** en **2,5 s**, puis replay `--repeat-each=2` **8/8** en **3,8 s**, port `54283`, sans retry nécessaire. Durées de tests uniquement, pas mesures de performance produit.
- Routes dédiées : `/sites`, `/login` (HTTP intercepté), `/e2e-accessibility/dialogs.html` (fixture navigateur montant les vrais PressFormDrawer et ProductionAssignmentEditor avec providers/styles réels, persistance simulée). Pour chacun des deux éditeurs : clic intérieur et glisser intérieur→extérieur conservés, clic `(10,100)` ferme au repos, ne ferme pas pendant mutation, Échap bloqué pendant attente puis fermeture/restauration après refus simulé, premier champ focalisé, boucle Tab/Maj+Tab et arrière-plan non focalisable.
- RTL accessibilité : **29/29** ; suite frontend complète finale : **22 fichiers, 180 réussis, 2 ignorés existants**. `npm run lint` complet, `npx tsc -b` et `git diff --check` réussis. Aucun changement du catalogue/API réalisé.
- Limite locale smoke : Vite standard refuse les polices provenant du node_modules lié hors racine ; les 36 tests passent avec fallback. La suite dédiée autorise explicitement ce chemin réel et charge les polices. Le lien temporaire est retiré, aucune dépendance installée. Ces vérifications ne prouvent ni parcours backend métier complet, ni performance, ni conformité WCAG globale.

Commandes de revue (depuis frontend, ports libres, serveurs propres) :

    CI=true PLAYWRIGHT_PORT=54284 npm run test:e2e -- --project=chromium
    CI=true A11Y_PORT=54283 npx playwright test --config playwright.accessibility.config.ts
    CI=true A11Y_PORT=54283 npx playwright test --config playwright.accessibility.config.ts --repeat-each=2
    CI=true npm test
    npm run lint
    npx tsc -b

## Vérification initiale (historique avant revue)

Preuves locales sans données utilisateur, identifiants réels ou jetons : `/tmp/iddrv-a11y-id/`.

- `before.log` : les **5 nouvelles régressions échouent** sur les fichiers de base remis temporairement dans ce seul worktree, puis tous les correctifs sont restaurés.
- `regression.log` : **5/5 passent** après correction, dont axe sur les trois dialogues sans désactivation de règle. RTL couvre aussi erreur auth et garde de validation source/annonce d’attente.
- `all-tests.log` : `npm test`, **22 fichiers, 180 tests réussis, 2 ignorés existants**. Aucun test axe existant supprimé/modifié ; l’exclusion definition-list déjà présente pour Workshop reste un risque documenté et hors périmètre.
- `types.log` : `npx tsc -b`, réussi.
- `lint.log` : ESLint ciblé sur tous les TS/TSX modifiés/nouveaux, réussi. `git diff --check`, réussi.
- `playwright.log` : **2/2 Chromium réels**, API HTTP interceptée avec fixtures synthétiques (pas mode démo, mais **pas API backend réelle non plus**). Navigation clavier seule depuis lien d’évitement jusqu’à création site, boucle, Échap/restauration, `:modal`, focus visible, menu mobile. Absence de débordement horizontal site/dialogue/login à 320 CSS px. Stress d’agrandissement du texte login par CSS, pas zoom navigateur natif.
- Captures `site-modal-320.png`, `login-text-200.png` ; traces sous `browser/*/trace.zip`. Elles contiennent seulement l’atelier fictif et `audit@example.test`, pas d’authentification effective ni mot de passe réel. Ne pas publier les traces brutes sans revue supplémentaire des sources embarquées.

Commandes frontend :

    npm test
    npx tsc -b
    A11Y_PORT=<port loopback libre> npx playwright test --config playwright.accessibility.config.ts

Les configs dédiées exigent `reuseExistingServer: false`, host `127.0.0.1`, `strictPort`, désactivent démo/skip-auth. Un port éphémère libre a été choisi à chaque lancement, aucun serveur utilisateur réutilisé/arrêté. `vite.accessibility.config.ts` autorise uniquement racine frontend et chemin réel du node_modules lié, afin de charger les polices réelles. Le lien temporaire vers le node_modules principal est retiré après vérification ; aucune installation/copie des dépendances.

## Impacts d’intégration et limites

- **Impact commun sur summary6** : la bordure globale input/select/textarea devient plus contrastée y compris dans monitoring et les autres écrans. `Layout` change l’annonce d’erreur et le focus du lien d’évitement pour toutes les routes. Vérifier visuellement les champs de summary6 après fusion. Aucun contrat API changé.
- AccessibleDialog est nouveau, adopté uniquement dans sites/presse/planning ; drawers restent alignés à droite. Les anciens wrappers ont été supprimés lors de la revue ; le dialog natif utilise la top layer au-dessus de la navigation mobile.
- Le fallback DOM sert jsdom sans top layer : la preuve d’inertie vient du test Chromium `:modal`, pas d’axe/RTL.
- Aucun lecteur d’écran humain testé. Axe jsdom ne mesure pas le contraste. Ratio documenté limité aux couleurs indiquées.
- Parcours API réels, expiration/renouvellement session, enregistrement et refus serveur réels non vérifiés dans ce lot.
- Reflow navigateur vérifié uniquement login/sites/dialogue site ; presse/planning bénéficient de limites de largeur et actions flex-wrap mais demandent encore une recette visuelle. Sources et planning testés au niveau composants, pas comme parcours navigateur métier complet.
- L’agrandissement CSS du texte n’est **pas** une preuve complète WCAG 1.4.4 ni un zoom navigateur natif à 200 %. Le zoom réel reste à exécuter.

## Recette humaine restante

1. Sur API de recette, compte à périmètre minimal : login valide/refusé/expiration, navigation clavier, déconnexion refusée puis réussie ; vérifier annonce sans double lecture avec NVDA/Firefox ou VoiceOver/Safari.
2. Créer/archiver site, créer/modifier presse (doublons code et ERP), connexion source invalide/pending/échec/réussite ; vérifier erreurs annoncées et correction puis disparition, Tab/Maj+Tab/Échap et restauration.
3. Planifier OF : ajout/retrait presses, doublon, fin avant début, conflit serveur, édition avec numéro désactivé, enregistrement long ; vérifier focus après retrait d’une ligne et fermeture après réussite.
4. Zoom navigateur **200 %**, viewport **320 CSS px**, texte long : aucune commande masquée, focus non recouvert, défilement du dialogue utilisable ; tester presse/planning/sources et les champs monitoring après intégration.
5. Audit contraste complet (texte secondaire sur fonds teintés, hover, erreurs, badges, graphes) et accessibilité des documents. Le point definition-list Workshop précédemment exclu d’axe reste à traiter dans un lot autorisé.
