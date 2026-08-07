# Rapport E3 — Intégration et mise en service du diagnostic

**Compétences :** C9 à C13 — **Pages cible :** 15–20 — **Statut :** brouillon rédigé (s'appuie sur E2 pour les métriques et le modèle HDT)

---

## 1. Architecture (C9)

Le pilote sépare **trois responsabilités** pour éviter qu'un score de ML devienne
une décision de production :

1. **Règles déterministes** — contrôlent les tolérances connues de la fiche de
   réglage versionnée : décision autoritaire sur le hors-tolérance ;
2. **HDT** (*Horizon de dérive sous tolérance*) — Isolation Forest
   contextualisée par machine : produit un **score d'anomalie** et une priorité
   d'inspection, sans commande machine ;
3. **`DeterministicInvestigator`** — produit les **hypothèses, preuves,
   contradictions et prochaine vérification** à partir du contexte machine, des
   baselines et des mesures disponibles.

```text
Cycles bruts → features causales → HDT IsolationForest
                                      ↓
                          score + seuil + signaux
                                      ↓
               DeterministicInvestigator + décision humaine
```

**Règle d'intégrité des données** : `data/scenarios/industrial_demo/ground_truth.json`
est réservé à l'évaluation. Il n'est lu **ni par le runtime, ni par l'API, ni par
les conteneurs** (vérifié par scan : `ground_truth_used: false` dans les
métadonnées de l'artefact).

## 2. API REST — C9

La route livrée est :

```http
POST /api/v1/process-drift
```

**Contrat d'entrée** (`ProcessDriftRequest`, validé Pydantic) :

- `site_id` (≥ 1) ;
- `cycles` : **3 à 1000 cycles bruts**, avec timestamp, `machine_erp_ref`
  **identique pour toute la fenêtre** (rejet 422 sinon) ;
- paramètres process disponibles (au moins une valeur non nulle sur les
  features numériques brutes, sinon 422).

**Contrat de sortie** (`ProcessDriftResponse`) :

```json
{
  "model_version": "hdt-process-drift-iforest-v1",
  "machine_erp_ref": "1003",
  "anomaly_score": 0.73,
  "predicted_instability_next_20_cycles": true,
  "threshold": 0.41,
  "horizon_cycles": 20,
  "signals": [
    {"feature": "cooling_time_s_volatility_20", "volatility": 0.72}
  ]
}
```

**Propriétés de la route** :

- **Authentifiée** : rôles viewer/analyst/supervisor/admin requis ;
- **Isolée par site** : `require_site(identity, payload.site_id)` — un client
  ne peut scorer que les machines de son site ;
- **Versionnée** : `model_version` renvoyé à chaque réponse ;
- **Erreurs explicites** : 422 pour contrat invalide (timestamps, multi-machines,
  features manquantes, historique vide), **503** si l'artefact est absent ou
  corrompu (l'erreur interne n'est jamais exposée au client) ;
- **Chargement paresseux** de l'artefact (`lru_cache`) avec validation du
  contrat runtime (clés requises, horizon, seuils finis).

## 3. Intégration React — C10

Le composant `ProcessDriftPanel` (`frontend/src/components/ProcessDriftPanel.tsx`)
affiche le score HDT avec tous ses états :

- **chargement** ;
- **absence de cycles bruts** — l'écran atelier affiche explicitement qu'aucune
  donnée n'est disponible tant qu'une source de cycles bruts réelle n'est pas
  raccordée (aucun score artificiel fabriqué à partir d'une timeline agrégée) ;
- **erreur récupérable** ;
- **état normal** ;
- **dérive détectée** : score, seuil, signaux (top 3 volatilités causales
  observées) et version du modèle ;
- **avertissement** : « priorité d'inspection, pas décision automatique ».

Le frontend ne transforme **jamais** les points de timeline agrégés en cycles
bruts : il affiche l'absence de données plutôt que d'inventer un score. Le mock
frontend reste déterministe pour les tests et la démonstration.

## 4. Évaluation — C11/C12

### Protocole

- Référence offline entraînée par `scripts/train_process_drift.py` ;
- **Split temporel 2/3 – 1/3 à l'intérieur de chaque machine** (jamais de split
  aléatoire) : 25 461 lignes train, 12 732 lignes test, 601 événements proxy
  train, 156 test ;
- Cible proxy : au moins 3 rebuts dans les 20 cycles futurs (label construit
  uniquement offline, jamais fourni à l'inférence).

### Résultats holdout synthétique

| Métrique | Résultat |
|---|---:|
| Average precision | **14,07 %** |
| Prévalence de référence | 1,23 % |
| Lift vs prévalence | **11,48×** |
| ROC-AUC | **0,878** |
| Precision au seuil machine | 12,29 % |
| Recall au seuil machine | 23,72 % |
| Taux d'alerte | **2,36 %** (301 / 12 732) |

**Lecture honnête** : le classement est utile sur le holdout synthétique
(~11,5× la prévalence), mais le score n'est **pas calibré en probabilité** et
aucune validation terrain n'est revendiquée.

### Tests automatisés (C12)

- `tests/test_process_drift.py` : contrat de features, features **causales**
  (pas de label courant), absence de lecture de `ground_truth.json`, modèle par
  machine, repli global machine inconnue, format de sortie, reproductibilité ;
- `tests/test_process_drift_api.py` : authentification, isolation par site,
  rejets 422/503, contrat de réponse ;
- `tests/test_process_drift_monitoring.py` : monitoring côté API ;
- `tests/test_rebut_risk.py` + `test_rebut_risk_api.py` : baseline logistique
  conservée ;
- `frontend/src/test/processDrift.test.tsx` : états du panneau UI.

## 5. Packaging et MLOps léger — C13

| Élément | Fichier |
|---|---|
| Code (features, split, entraînement, prédiction) | `ml/process_drift.py` |
| Commande reproductible | `scripts/train_process_drift.py` |
| Artefact | `models/process_drift_hdt_v1.joblib` |
| Métadonnées (version, contrat, split, métriques) | `models/process_drift_hdt_v1.meta.json` |
| Monitoring (distribution des scores, taux d'alerte) | `ml/monitoring.py` + `backend/app/metrics.py` |
| Tests pipeline | `tests/test_process_drift*.py` |
| Tests UI | `frontend/src/test/processDrift.test.tsx` |

**Métadonnées versionnées** (`meta.json`) : `model_version`, `feature_columns`,
`anomaly_features`, `target_column`, `horizon_cycles`, `baseline_window`,
`metrics` (AP, ROC-AUC, precision/recall, lift, alert_rate), `rows`,
`time_boundary` (split temporel), `contract` (features causales, population
normale `scrap_flag=0`, split chronologique par machine, **`ground_truth_used: false`**).

**Monitoring (C11)** : la prédiction est enregistrée en **side-channel** —
`ml/monitoring.py` (distribution des scores, taux d'alerte) et métriques
Prometheus (score, alerte, latence d'inférence) — qui ne peut jamais modifier
la réponse ni faire échouer la requête. Le feedback humain sur les
investigations existe déjà (boucle qualité).

**Promotion en production** (conditions explicites, non remplies aujourd'hui) :
données terrain, label SPC/qualité validé, surveillance du taux d'alerte et du
drift, abstention hors domaine, validation humaine. Statut présenté :
**« prototype offline évalué, prêt à qualifier »** — pas « déployé » ni
« validé terrain ».

## 6. Démonstration (préparée)

1. Lancer l'entraînement reproductible : `python scripts/train_process_drift.py` ;
2. Lancer les tests : `python -m pytest -q tests/test_process_drift*.py` ;
3. Appeler `POST /api/v1/process-drift` avec une fenêtre de cycles bruts
   (`data/cycles_bruts/machine_cycles_bruts_1003.csv`) ;
4. Montrer le score, le seuil, les signaux et la version ;
5. Montrer le refus d'une fenêtre agrégée sans cycles bruts (422) ;
6. Lancer `DeterministicInvestigator` sur un incident : hypothèses, preuves,
   feedback humain.

## 7. Limites assumées

- Métriques **offline synthétiques** ; score non calibré, non causal ;
- L'écran atelier s'abstient tant que les cycles bruts réels ne sont pas
  raccordés (le jeu `data/cycles_bruts/` est une simulation réaliste, hors
  domaine partiel — taux d'alerte 18,5 % vs 2,4 % attendu) ;
- Pas de monitoring continu en production, pas d'abstention formelle hors
  domaine : à construire avant déploiement ;
- Aucune action automatique sur les presses.

## 8. Conclusion

Le service IA du pilote est **explicable par construction** : l'API expose un
score versionné, protégé et isolé par site ; le frontend affiche une priorité
d'inspection ; l'investigateur déterministe reste responsable des preuves ;
l'humain décide. Le packaging est reproductible et les métadonnées tracent le
contrat, le split et les métriques. L'ensemble est **« prêt pour pilote »**,
avec une qualification terrain comme prochaine étape.

## 9. Preuves

- `backend/app/api/process_drift.py`, `backend/app/schemas.py`, `backend/app/security.py`
- `frontend/src/components/ProcessDriftPanel.tsx`, `frontend/src/lib/api.ts`, `frontend/src/pages/WorkshopPage.tsx`
- `ml/process_drift.py`, `ml/monitoring.py`, `scripts/train_process_drift.py`
- `models/process_drift_hdt_v1.joblib` + `.meta.json`
- `tests/test_process_drift.py`, `tests/test_process_drift_api.py`, `tests/test_process_drift_monitoring.py`, `tests/test_rebut_risk*.py`
- `frontend/src/test/processDrift.test.tsx`
- `ml/HDT-certification-update.md`, `ml/VALIDATION-HDT.md`, `ml/README.md`
