# C14–C16 — propositions de recette, pas résultats

9 septembre 2026. Tests applicatifs/réseau non exécutés dans ce lot. Les cinq tests données ne sont ni recette utilisateur ni audit d'accessibilité. Toute stack doit être isolée (ports, volumes, projet Compose, comptes synthétiques), sans lecture des secrets ni connexion à la production. Pas d'installation navigateur/dépendances lourdes implicite.

## Parcours et histoires proposés

Schéma fonctionnel : connexion → choix site autorisé → atelier/machine → données contextualisées → signal de dérive → examen humain. Alternatives : accès refusé, session expirée, site vide, données absentes/périmées, erreur réseau, retour navigation. Ne pas remplacer un état vide par des valeurs inventées.

| Histoire / contexte | Scénario et acceptation fonctionnelle | Objectif accessibilité proposé WCAG 2.2 |
|---|---|---|
| Utilisateur habilité consulte son site | Login réel, session persistée, navigation atelier et machine ; autre site masqué, déconnexion puis accès refusé | 2.1.1 clavier ; 2.4.7 focus visible ; 3.3.2 labels explicites |
| Analyste examine des données | Valeurs/horodatages comparés aux fixtures connues persistées ; vide/retard/erreur différenciés | 1.4.1 information non portée seulement par couleur ; 1.3.1 relations tableau ; 4.1.3 messages d'état |
| Utilisateur examine un signal | Provenance/version et limites visibles ; ne pas confondre dérive et défaut certain | 1.4.3 contrastes texte ; 1.4.10 reflow ; 2.4.3 ordre de focus |

Ces objectifs doivent être approuvés et étendus à chaque story ; ils ne sont pas une attestation WCAG/RGAA. Faire mesurer contraste, zoom 200/400 %, clavier seul (tab/shift-tab/entrée/échappement), absence de piège, noms accessibles, annonces d'erreur/chargement et lecture tableau par lecteur d'écran. Consigner navigateur/OS/outil/version, page, étape, attendu/obtenu, capture sans donnée personnelle et ticket d'écart.

## Commandes préparées pour environnement déjà provisionné et autorisé

```sh
cd frontend
# Liste uniquement : pas preuve d'exécution, ne doit pas télécharger de package.
./node_modules/.bin/playwright test --config playwright.integration.config.ts --list
# Après contrôle humain URL localhost, comptes/volumes exclusivement synthétiques :
./node_modules/.bin/playwright test --config playwright.integration.config.ts e2e-integration/navigation-smoke.spec.ts e2e-integration/site-isolation.spec.ts --reporter=list
```

Configurer préalablement les variables attendues par les tests (`IDDRV_E2E_BASE_URL`, comptes de test, IDs de sites/machines) sans imprimer mot de passe/token. Relire les tests sélectionnés : valeurs manquantes peuvent provoquer **skip** ; zéro assertion exécutée n'est pas succès de recette. Le parcours étendu existant `production-flow.spec.ts` requiert en plus fixture HTTP, fichiers d'import/correction et contrôle de fixture ; il effectue des mutations. Ne pas le lancer sans inventaire et autorisation du bac à sable, et ne pas fabriquer un nouveau simulateur pour lever ce prérequis.

Contrôle C5 à préparer sur la même stack : exporter `/openapi.json`, recenser tous endpoints/security schemes puis vrai login `/api/v1/auth/login`, lecture authentifiée et comparaison aux données persistées, lecture anonyme, autre site, droits insuffisants, expiration/révocation. Ne conserver aucun cookie/token dans preuve. L'export OpenAPI seul ne prouve pas restrictions ni exhaustivité métier.

## Conditions de fin et décision

Rapport recette avec SHA commit, versions, topologie isolée, préparation, commande exacte expurgée, code retour, nombres passed/failed/skipped, traces expurgées et anomalies. Les mocks Playwright/unitaires restent utiles pour régression mais ne prouvent pas persistance, réseau, auth réelle ou usage humain. Une recette automatisée ne dispense pas de contrôles manuels d'accessibilité.

Avis POC proposé : poursuivre expérimentation isolée, pas usage industriel tant que sources/SQL réel, parcours auth/persistance, accessibilité et pertinence du signal restent non validés. Commanditaire doit rendre décision go/no-go datée sur résultats observés. C16 nécessite un vrai tableau partagé, responsables consentants, cycles et retours contemporains ; ce document ne remplace ni réunions ni validation client.
