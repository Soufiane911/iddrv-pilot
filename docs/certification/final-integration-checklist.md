# IDDRV — Checklist d'intégration finale des handoffs

## Contexte

Ce document guide l'intégration des handoffs des trois terminaux d'implémentation (1, 2 et 3) dans le cadre de la validation croisée finale certifiante DEVIA RNCP37827.

**État courant :** G6 PASS, 75+ tests Python verts, 2 tests Vitest verts, frontend build OK, Docker Compose valide.
**Orchestrateur :** session courante, propriétaire exclusif de `.github/workflows/` et `docs/certification/`.

---

## Phase 0 — Prérequis avant intégration

- [ ] **Vérifier le dépôt** : `git status`, `git log --oneline -5`
- [ ] **Confirmer qu'aucun agent n'a commité** : vérifier que seul l'orchestrateur a créé des commits
- [ ] **Vérifier les ownerships** : chaque agent n'a touché que son périmètre autorisé
- [ ] **Lire AGENTS.md** : les règles de propriété et de sécurité sont toujours en vigueur

## Phase 1 — Réception des handoffs

Pour chaque terminal (1, 2, 3), examiner :

- [ ] **Terminal 1** — Handoff reçu : OUI / NON
  - [ ] Fichiers modifiés : _____
  - [ ] Ownership respecté : OUI / NON
  - [ ] Tests passés : OUI / NON
  - [ ] Risques identifiés : _____
  - [ ] Blocages : _____

- [ ] **Terminal 2** — Handoff reçu : OUI / NON
  - [ ] Fichiers modifiés : _____
  - [ ] Ownership respecté : OUI / NON
  - [ ] Tests passés : OUI / NON
  - [ ] Risques identifiés : _____
  - [ ] Blocages : _____

- [ ] **Terminal 3** — Handoff reçu : OUI / NON
  - [ ] Fichiers modifiés : _____
  - [ ] Ownership respecté : OUI / NON
  - [ ] Tests passés : OUI / NON
  - [ ] Risques identifiés : _____
  - [ ] Blocages : _____

## Phase 2 — Validation globale

Exécuter dans l'ordre :

```bash
# 1. Tests Python (hors E2E)
python -m pytest -q

# 2. Tests E2E sur base isolée (tiers 1 et 2)
python tests/e2e/run_tests.py -t 1,2

# 3. Validation Docker Compose
docker compose config --quiet

# 4. Frontend lint
npm --prefix frontend run lint

# 5. Frontend tests (Vitest)
npm --prefix frontend run test

# 6. Frontend build
npm --prefix frontend run build
```

### Résultats

| Commande | Résultat attendu | Résultat obtenu | OK ? |
|---|---|---|---|
| `python -m pytest -q` | Tous verts | | |
| `python tests/e2e/run_tests.py -t 1,2` | 50 passed, 0 failed | | |
| `docker compose config --quiet` | Pas d'erreur | | |
| `npm --prefix frontend run lint` | Pas d'erreur | | |
| `npm --prefix frontend run test` | 2 passed | | |
| `npm --prefix frontend run build` | Succès | | |

## Phase 3 — Régression et preuves manquantes

- [ ] **Régressions Python** : comparer le nombre de tests passés avant/après intégration
- [ ] **Régressions frontend** : vérifier lint, Vitest, build
- [ ] **Nouvelles erreurs dans les logs** : vérifier `docker compose logs`
- [ ] **Ownership non respecté** : identifier tout fichier modifié hors périmètre autorisé
- [ ] **Secrets exposés** : grep `password|secret|token|key` dans les nouveaux fichiers
- [ ] **Preuves manquantes dans la coverage-matrix** : mettre à jour `docs/certification/coverage-matrix.md` si de nouvelles compétences sont couvertes

## Phase 4 — Vérification de la matrice de certification

- [ ] **C1 à C21** : chaque compétence a un fichier, un test et une démonstration identifiables
- [ ] **Aucune compétence marquée comme « prouvée » sans preuve vérifiable**
- [ ] **Les preuves sont reproductibles** : les commandes de test donnent le même résultat

## Phase 5 — Mise à jour de la documentation

- [ ] Mettre à jour `docs/implementation-status.md` si les gates ont progressé
- [ ] Mettre à jour `docs/certification/coverage-matrix.md` si nécessaire
- [ ] Documenter tout nouveau risque ou limitation dans le handoff

## Phase 6 — CI et workflows

- [ ] Vérifier la syntaxe YAML des workflows (voir note ci-dessous)
- [ ] Confirmer que les permissions sont minimales (`contents: read`)
- [ ] Si le remote GitHub est configuré, lancer manuellement la CI
- [ ] Sinon, capturer les exécutions locales comme preuves

## Note sur la vérification de syntaxe YAML des workflows

```bash
# Vérification basique (pas de GitHub Actions CLI en local)
python3 -c "
import yaml, sys
for f in ['.github/workflows/ci.yml', '.github/workflows/delivery.yml']:
    try:
        with open(f) as fh:
            yaml.safe_load(fh)
        print(f'{f}: syntaxe OK')
    except Exception as e:
        print(f'{f}: ERREUR {e}')
        sys.exit(1)
"
```

---

## Sign-off

- [ ] Toutes les phases ci-dessus sont complétées
- [ ] La coverage-matrix confirme 21/21 compétences prouvées
- [ ] Aucune compétence n'est marquée comme prouvée sans fichier/test/démonstration identifiable
- [ ] Les trois terminaux ont rendu leurs handoffs et l'intégration est validée
