# Summary6 — vérification finale de la branche replay

Base de contrôle : `f194d6ea54b0eea68e9f0f4ea9c918169c98a5a2`, incluant main `d69c5a4b` et les correctifs de revue. Ce document est ajouté ensuite sans changement du moteur ni du paquet.

## Paquet approuvé, privé et non distribué dans Git

- Runtime : `summary6-0c8b4c15cd4df33784468dfcd2057b52261122a8c90dbb0b1ba4a117b2870702`.
- SHA256 manifeste : `919fc41c58d1e821f9dcf7e16ee6c317e5966d4ec1c2444ad96045289543f4ff`.
- SHA256 modèles : `3de68e2dba256aab7e6d79d2acd6e0e74b915a20efe3046e5cbfeb22a696f915`.
- Code courant vérifié contre les empreintes du manifeste avant chargement. Environnement Python3.13.9/sklearn1.7.2 et autres versions strictes décrites dans le manifeste.
- Installation privée durable locale vérifiée ; la présence du code sur GitHub ne distribue ni n'active ce paquet. Aucun autre candidat exécuté, aucun remplacement d'artefact historique.

## Vérifications réelles

- Parent : suite Python `tests --ignore=tests/e2e` avec `SUMMARY6_TEST_PACKAGE` et pin approuvé : **745 passed, 37 skipped, 35 subtests passed**, 26,82s. En CI sans paquet privé, les tests de ses scores sont explicitement ignorés : ces résultats ne doivent pas être attribués à un run GitHub.
- Parent : frontend complet **193 passed, 2 skipped** ; lint complet et `npm run test:build-context` réussis.
- Reviewer final : suites runtime/package/API/hardening, **92 passed**, aucun skip ; aucun P1/P2 restant identifié dans ce périmètre ciblé.
- Reviewer final : smoke HTTP localhost réel avec paquet approuvé, PostgreSQL temporaire tmpfs, login/session DB, refus anonyme401 et autre site403. Aucun incident ajouté, conteneur propriétaire supprimé.
- Rejeu réel : cutoffs59/79/83 abstention ;84/399 available. Scores de décision au84 : `0.4179955185182244`, au399 : `0.455445834063937`. Un score calculé avant84 n'est pas une décision publiable.
- Parent : Chromium dédié, **2 passed** : atelier conservé en mode summary6_replay et disabled, accès planning, absence POST historique. API interceptée : ce n'est pas le navigateur branché à la vraie API du smoke. Polices de secours utilisées à cause de la restriction Vite sur le lien local node_modules ; pas de validation visuelle exhaustive/3D.

Commandes reproductibles (paquet installé par opérateur, chemins privés hors dépôt) :

```sh
SUMMARY6_TEST_PACKAGE="$SUMMARY6_PACKAGE_DIR" SUMMARY6_TEST_MANIFEST_SHA256="$SUMMARY6_MANIFEST_SHA256" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest -q tests --ignore=tests/e2e
npm --prefix frontend run test
npm --prefix frontend run lint
npm --prefix frontend run test:build-context
# Depuis frontend/, choisir un port loopback libre :
SUMMARY6_UI_INTERCEPT=true SUMMARY6_UI_PORT=5189 npx playwright test --config playwright.summary6.config.ts
```

Voir les scripts lancement/smoke et [durcissement API](summary6-api-hardening.md) pour les variables et gardes ; ne pas diriger un exercice destructif vers une base utilisateur.

## Conditions de fusion et d'activation

1. Vérifier CI de la PR et intégrer les corrections nécessaires ; aucune fusion automatique.
2. `HDT_RUNTIME_MODE` absent/inconnu = scoring désactivé. `summary6_replay` doit être choisi explicitement avec paquet et pin ; rollback historique uniquement avec `historical` explicite. La fusion seule n'active pas summary6.
3. Readiness vérifie les six lots ; admission limitée à une requête simultanée par identité et deux par processus. Utiliser le lanceur mono-worker ; pas de quota distribué ni par minute revendiqué.
4. Replay synthétique sur contextes M1/M2/M3×R1/R2 uniquement ; pas de mapping des presses152/1003/606 ni de live raccordé. Le contexte/run/recette connu à temps et l'historique causal restent à intégrer pour le live.
5. Atelier/planning/presses restent accessibles, frontière limitée au scoring. Vérifier la compatibilité visuelle avec la PR accessibilité lors de sa fusion.
6. Confirmation scientifique summary6 non satisfaite sur tous les jeux ; aucune performance industrielle ni acquisition globale C1–C21 déduite de ces tests.

Traces locales éphémères : `/tmp/iddrv-summary6-final-review/` (identité/tests/smoke), `/tmp/iddrv-summary6-parent-{full,ui,build,browser}.log`. Ne pas confondre captures API interceptée, tests unitaires et exécution réseau réelle.
