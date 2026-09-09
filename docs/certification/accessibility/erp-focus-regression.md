# Régression ERP / focus — PR #5

## Versions et isolation

Vérification locale du 9 septembre 2026 :

- Branche : `feat/accessibility-c10-c17`, HEAD testé `36b6dce94b5c631b9b856734dc519ca6b60cec62`, plus le nouveau test.
- Référence publiée confirmée par `git ls-remote origin refs/heads/feat/accessibility-c10-c17` : même SHA (`remote.log`). Aucun push.
- Baseline main : `d69c5a4b48f0fdce53a60669a748295db868cf5e`, ancêtre du HEAD testé.
- Baseline extraite intégralement avec `git archive <SHA> | tar -x -C <temp>` dans `/tmp/iddrv-main-baseline.o9iOYt`. Seul le nouveau test y a été ajouté. Aucun checkout/revert ni changement de production dans la branche PR.
- Les deux répertoires utilisent les dépendances locales existantes `/Users/soufianehamzaoui/Desktop/EPSI/ProjetSeptembre/frontend/node_modules`. Le lien préexistant `frontend/node_modules` de la PR est conservé, non versionné. Aucune installation.
- Node `26.6.0`, npm `11.18.0`, React/React DOM `18.3.1`, React Query `5.101.2`, Testing Library React `16.3.2`, user-event `14.6.4`, jest-dom `6.9.1`, Vitest `4.1.10`, jsdom `25.0.1`, TypeScript `5.9.3`, ESLint `9.39.4`, Vite `6.4.3`.
- SHA256 identique du test dans les deux arbres : `aaa7fd9e3f3dddd52688a45f4d9f04157020a2dd99d444edafdc92087f2c828e`.
- SHA256 identique des deux `package-lock.json` : `1d37098211a1af9b0c5657a7812390d4649fe2f5b8f15039d1310372f57a2d76`. Dépendances réutilisées, pas une réinstallation CI propre ; inventaire réellement installé dans `versions.log`.

## Expérience déterministe

`frontend/src/test/pressFormRerender.test.tsx` monte le vrai `PressFormDrawer`, avec un vrai provider React Query et une API espionnée uniquement à la frontière de sauvegarde. La machine en édition, le client, le provider, `open`, `siteId`, `api` et `onSaved` restent stables. Seule l'identité de `onClose` change via `rerender` après la saisie ERP.

Deux variantes vérifient les valeurs des cinq champs, le focus ERP, le payload exact d'un unique `updateMachine(8, ...)`, l'absence de création et l'appel de `onSaved` :

1. Saisir `ERP-608`, remplacer `onClose`, sauvegarder.
2. Saisir `ERP`, remplacer `onClose`, poursuivre avec `user.keyboard('-608')` sans recliquer le champ, sauvegarder.

Un troisième test vérifie qu'Échap appelle exactement une fois le **nouveau** callback et jamais l'ancien, sans sauvegarde. Aucun délai artificiel, aucun mock d'effet/dialogue, aucun retry Vitest. Les assertions `expect.soft` restent obligatoires et font échouer le test ; elles permettent de voir ensemble la perte de focus, la valeur effacée et le véritable payload envoyé, plutôt que d'arrêter au premier symptôme.

### Résultat baseline

Les deux variantes échouent, Échap passe. Résultat identique sur **10 exécutions indépendantes**, sans retries :

- Après le seul remplacement du callback : ERP vide et focus déplacé vers le nom.
- Variante 1 : `erp_ref: null`, au lieu de `ERP-608` dans le payload.
- Variante 2 : `erp_ref: null` et `name: 'Presse sans ERP-608'`, au lieu de `Presse sans ERP`.

Cela démontre le mécanisme indépendamment du timing des requêtes de `WorkshopPage`. Dans main, l'effet d'initialisation dépend de `[machine, onClose, open]` et réinitialise les champs puis focalise le nom. `WorkshopPage.tsx:283` fournit effectivement un callback inline. Dans PR #5, l'initialisation dépend de `[machine, open]`, et `AccessibleDialog` initialise le focus au montage sans le refaire sur chaque callback ; le contrat de callback courant est conservé.

### Résultat PR #5

| Vérification | Résultat final | Log |
| --- | --- | --- |
| Nouveau test seul | 3/3 passent, exit 0 | `current.log` |
| Baseline, nouveau test seul | 2 échecs / 1 succès, exit 1 | `baseline.log` |
| Baseline répétée 10 fois | 10 fois les mêmes 2 échecs, exit 1 | `baseline-1.log` à `baseline-10.log`, `baseline-repetitions.log` |
| `workshopSetup` + nouveau test, 10 processus indépendants | 10/10 passent, 6 tests par exécution, exit 0 | `workshop-1.log` à `workshop-10.log`, `repetitions.log` |
| Suite frontend complète | 23 fichiers passent ; 183 tests passent, 2 ignorés existants, exit 0 | `full.log` |
| TypeScript app + config Node | exit 0 | `tsc.log` |
| Lint, zéro warning autorisé | exit 0 | `lint.log` |

Tous les logs sont sous **`/tmp/iddrv-erp-regression.l71qsT/`**. Un premier typecheck a détecté l'absence de `soft` sur le type global `Expect` (`tsc-initial.log`) ; corrigé par l'import explicite de `expect` depuis Vitest dans le seul nouveau test. Tous les résultats finaux ci-dessus ont été rejoués sur ce fichier corrigé.

## Commandes de reproduction

Depuis le répertoire `frontend` de chaque arbre, test comparatif identique :

```sh
npm test -- src/test/pressFormRerender.test.tsx --retry=0
```

Depuis `frontend` de la PR :

```sh
for n in $(seq 1 10); do
  npm test -- src/test/workshopSetup.test.tsx src/test/pressFormRerender.test.tsx --retry=0
  # Conserver chaque log et code de sortie, sans arrêter au premier échec.
done
npm test -- --retry=0
./node_modules/.bin/tsc -p tsconfig.app.json --noEmit --incremental false
./node_modules/.bin/tsc -p tsconfig.node.json --noEmit --tsBuildInfoFile /tmp/iddrv-erp-regression.l71qsT/node.tsbuildinfo
npm run lint
```

## Portée de la conclusion

Preuve d'un bug de main reproductible à la demande et de sa non-régression sur le code actuel de PR #5. Les symptômes reproduits sont compatibles avec les échecs ERP signalés en CI PR #4/#6, y compris l'écriture dans le mauvais champ. Ce test ne trace cependant pas le rerender exact des anciens jobs CI et ne prouve pas que **chaque** échec intermittent avait cette cause unique. Les dix passages locaux de `workshopSetup` ne garantissent pas l'absence universelle de flakiness. Test DOM/jsdom, pas une nouvelle certification navigateur ou backend.

Seuls le nouveau test et ce rapport sont ajoutés ; aucun assouplissement des tests existants, aucun changement de production, aucun push ni modification de main.
