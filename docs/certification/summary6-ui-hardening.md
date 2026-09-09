# Durcissement UI summary6 — atelier et confirmation runtime

## Périmètre

La frontière runtime ne remplace plus `WorkshopPage`. Le plan 2D/3D, la barre d’atelier, le catalogue/CRUD presses, la passerelle et son mapping, le contexte de production et le lien planning restent disponibles lorsque le replay synthétique est sélectionné, désactivé ou indisponible.

Un panneau de scoring séparé porte `RuntimeBoundary`. Le panneau historique `ProcessDriftPanel` et ses hooks de POST ne sont montés qu’après une confirmation réussie de `/summary6/current` obtenue après montage de l’observateur. Une valeur historique préchargée dans QueryClient n’est pas une autorisation. Pendant un refetch, une pause réseau ou après une erreur de refetch, aucun enfant de calcul historique n’est monté. L’observateur reste monté et le bouton de reprise est accessible : pas de boucle provoquée par le montage des enfants.

Les GET métier de l’atelier restent consultables. Les incidents archivés gardent leurs routes et leur identité. Les indicateurs atelier sont explicitement séparés de summary6 ; le panneau de prédiction historique n’est pas réutilisé pour présenter des résultats synthétiques. Le monitoring garde sa navigation technique même si le runtime est indisponible. Sa référence HDT par défaut ne prétend pas attester un paquet chargé.

## Contrat UI/API

- Site atelier repris de `/sites/:siteId/workshop`, vérifié dans les sites autorisés retournés par API. Aucun remplacement par le site 1 ni sélecteur déconnecté de l’atelier. Le sélecteur du monitoring se justifie par son contexte multi-sites.
- Sources et lots repris sans traduction des identifiants API. Aucune transformation d’unités.
- Formulaire et cache des lots partitionnés par site et paquet chargé ; changement de site/paquet supprime sélection et résultat antérieurs.
- Identité de réponse vérifiée : site, paquet et compteur inclus.
- `latest.status = available | abstained` respecté. Les raisons, notamment `numerical_failure`, restent génériques et n’inventent aucune décision.
- État `ready`, activation du replay, paquet chargé et catalogue réussi requis. Contrôles de lot/compteur/calcul bloqués pendant le POST ou l’indisponibilité du catalogue.
- Erreurs 401/403, 409, 503 et 429 expliquées ; `Retry-After` conservé depuis la réponse HTTP et affiché sans transformer un HTTP-date en secondes. Aucun fallback de calcul historique.
- **Borne contractuelle actuelle : 400 observations maximum, compteurs zéro-indexés 0–399.** Le frontend calcule `maxCutoff = min(400, countDuLot) - 1`. Il refuse 400 comme compteur inclus, conformément au `Field(le=399)` de l’API présente. Une exigence de compteur inclus 400 nécessiterait un changement coordonné du contrat backend ; elle n’est pas simulée uniquement dans le label UI.

## Vérifications reproductibles

Depuis `frontend`, avec les dépendances existantes du dépôt parent (lien temporaire, sans installation) :

- `npm test` : suite complète Vitest, notamment cache historique préchargé + réponse summary6 différée, échec de revalidation, erreurs HTTP, changement de site/paquet, contrôles pending et readiness false.
- `npm run build` : types TypeScript et build Vite.
- `npm run lint` : ESLint sans avertissement.
- `SUMMARY6_UI_INTERCEPT=true SUMMARY6_UI_PORT=<port libre> npx playwright test --config playwright.summary6.config.ts` : Chromium, serveur temporaire uniquement sur 127.0.0.1, strictPort, aucun serveur utilisateur réutilisé. Deux scénarios : summary6 et disabled. API explicitement interceptée ; vrai routeur/page atelier, plan 2D, catalogue, accès passerelle, navigation planning et contrôle des POST. Le replay vérifie le payload et rend une abstention numerical_failure.

Résultat de cette passe : 24 fichiers Vitest verts, 193 tests réussis et 2 ignorés ; build/types et lint verts ; 2 tests Chromium dédiés réussis. Le lien temporaire `frontend/node_modules` a été retiré. Les logs locaux sont `/tmp/summary6-ui-{full,build,lint,playwright}.log`.

La suite navigateur dédiée est exclue de la configuration démo standard sans activation explicite. Elle ne certifie ni le package ML réel, ni l’auth serveur, ni la compatibilité GPU 3D. Les fontes du lien node_modules parent déclenchent des refus de la liste Vite fs.allow dans ce montage temporaire ; les tests fonctionnels passent avec les fontes de secours. Aucun changement de Layout/CSS commun n’a été fait.

Les tests React de vraie page conservent les outils en modes prêt, disabled et erreur ; ils suivent effectivement le lien planning. Un cas change le site URL puis visite un site non autorisé et vérifie l’absence de GET lots pour ce site et de fallback site 1.

## Limites et coordination

L’a11y globale reste le périmètre de la PR parallèle : intégrer ensuite ses Layout/CSS et revalider navigation clavier, focus, contraste et présentation du nouveau panneau (desktop/mobile). La navigation d’archives reste disponible via les incidents métier ; aucun import de l’historique localStorage HDT dans summary6. Aucun stage, commit ou push effectué par ce lot frontend.
