# Épreuve E3 — Intégration et mise en service du diagnostic

**Compétences :** C9 à C13 — **Durée :** 15 minutes

## Message central

Le pilote sépare trois responsabilités :

1. les règles déterministes contrôlent les tolérances connues ;
2. HDT priorise une inspection grâce à un score d'anomalie multivarié ;
3. `DeterministicInvestigator` produit les hypothèses et preuves explicables.

HDT est versionné et exposé par une API sécurisée, mais reste un prototype sur
données synthétiques. Il ne déclenche aucune commande automatique.

## 1. Architecture

```text
Cycles bruts → features causales → HDT IsolationForest
                                      ↓
                              score + seuil + signaux
                                      ↓
                   DeterministicInvestigator + décision humaine
```

Le fichier `ground_truth.json` est réservé à l'évaluation et n'est lu ni par le
runtime, ni par l'API, ni par le conteneur.

## 2. API REST — C9

Route livrée :

```http
POST /api/v1/process-drift
```

Contrat d'entrée :

- `site_id` ;
- au moins trois cycles bruts ;
- timestamp ;
- `machine_erp_ref` identique pour la fenêtre ;
- paramètres process disponibles.

Contrat de sortie :

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

La route est authentifiée, isolée par site, versionnée et renvoie une erreur
503 si l'artefact est absent. Une fenêtre agrégée sans paramètres process bruts
est rejetée ; elle ne doit pas être transformée en score artificiel par
imputation.

## 3. Intégration React — C10

Le composant `ProcessDriftPanel` affiche :

- chargement ;
- absence de cycles bruts ;
- erreur récupérable ;
- état normal ;
- dérive détectée ;
- score, seuil, signaux et version ;
- avertissement « priorité d'inspection, pas décision automatique ».

L'écran atelier ne transforme volontairement pas les points de timeline agrégés
en cycles bruts. Il affiche donc l'absence de données jusqu'au raccordement d'une
source de cycles bruts réelle. Le mock frontend reste déterministe pour les tests
et la démonstration.

## 4. Évaluation — C11/C12

La référence offline est entraînée par `scripts/train_process_drift.py` et
évaluée par split temporel par machine.

| Métrique | Résultat holdout synthétique |
|---|---:|
| Average precision | 14,07 % |
| Prévalence | 1,23 % |
| Lift | 11,48× |
| ROC-AUC | 0,878 |
| Precision | 12,29 % |
| Recall | 23,72 % |
| Taux d'alerte | 2,36 % |

Les tests vérifient le contrat de features, l'absence du label courant à
l'inférence, les features causales, le packaging, le modèle par machine, le
fallback global, l'API, l'authentification, l'isolation site et le rejet des
historiques agrégés sans variables process.

Ces métriques sont une preuve de faisabilité sur données synthétiques. Le score
n'est pas calibré en probabilité et aucune validation terrain n'est revendiquée.

## 5. Packaging et MLOps léger — C13

- `ml/process_drift.py` : features, entraînement et prédiction ;
- `scripts/train_process_drift.py` : commande reproductible ;
- `models/process_drift_hdt_v1.joblib` : artefact ;
- `models/process_drift_hdt_v1.meta.json` : version, contrat, split et métriques ;
- `tests/test_process_drift.py` : tests du pipeline ;
- `tests/test_process_drift_api.py` : tests de l'API ;
- `frontend/src/test/processDrift.test.tsx` : tests UI.

La promotion en production nécessitera des données terrain, un label SPC/qualité
validé, la surveillance du taux d'alerte et du drift, une abstention hors domaine
et une validation humaine.

## 6. Démonstration

1. lancer le modèle et les tests ;
2. appeler `/api/v1/process-drift` avec une fenêtre de cycles bruts ;
3. montrer le score et ses signaux ;
4. montrer que le panneau UI refuse les agrégats sans cycles bruts ;
5. lancer `DeterministicInvestigator` sur l'incident ;
6. afficher les preuves et enregistrer le feedback humain.

## Réponse orale recommandée

> « L'API n'expose pas une décision automatique. Elle expose un score HDT
> versionné, protégé par authentification et isolé par site. Le frontend affiche
> une priorité d'inspection. L'investigateur déterministe reste responsable des
> preuves et l'opérateur garde la décision. Le modèle est livré comme prototype
> offline ; sa validation terrain est une étape distincte. »

## Preuves

- `backend/app/api/process_drift.py`
- `backend/app/schemas.py`
- `frontend/src/lib/api.ts`
- `frontend/src/components/ProcessDriftPanel.tsx`
- `frontend/src/pages/WorkshopPage.tsx`
- `ml/process_drift.py`
- `scripts/train_process_drift.py`
- `tests/test_process_drift.py`
- `tests/test_process_drift_api.py`
- `frontend/src/test/processDrift.test.tsx`
- `ml/HDT-demo-script.md`
