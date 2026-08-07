# HDT — Horizon de dérive sous tolérance

## 1. Problème métier

Une fiche de réglage sait dire qu'une valeur est hors tolérance. Une règle
univariée est donc préférable au ML pour ce cas précis. Le sujet HDT traite la
zone complémentaire : chaque variable peut encore être acceptable, mais la
variabilité conjointe du procédé augmente et annonce une instabilité future.

Le modèle répond à la question suivante :

> La trajectoire récente de cette machine est-elle suffisamment inhabituelle
> pour justifier une inspection avant une séquence qualité instable ?

Le résultat est une aide à la décision. Il ne déclenche ni arrêt automatique ni
modification automatique de la presse.

## 2. Décision et cible

Un cycle est l'unité d'analyse. La fenêtre d'anticipation est de 20 cycles.
Pour rendre le prototype mesurable avec les données disponibles, le label
offline est :

```text
instability_next_20_cycles = 1
si au moins 3 scrap_flag apparaissent dans les 20 cycles suivants
```

Cette définition ne regarde que le futur pour construire la cible. Le cycle
courant et les cycles précédents servent uniquement aux features. Le seuil de
3 rebuts est un **proxy synthétique de séquence instable**, pas une vérité
industrielle universelle.

En production, ce proxy doit être remplacé par un événement validé :

- excursion hors tolérance persistante pendant `k` cycles ;
- alarme SPC validée par le responsable process ;
- dérive qualité mesurée sur masse, cote, warpage ou aspect ;
- intervention opérateur qualifiée.

## 3. Données et prévention des fuites

Sources utilisées : `machine_cycles_*.csv` uniquement.

Le pipeline n'utilise pas :

- `ground_truth.json` ;
- `quality_flag` ;
- `defect_type` ;
- `production_order_id` comme identifiant prédictif ;
- une mesure qualité postérieure au cycle comme feature.

`scrap_flag` est utilisé offline uniquement :

1. pour construire le label futur ;
2. pour sélectionner les cycles historiques normaux utilisés par
   l'Isolation Forest.

Il n'est jamais fourni au modèle au moment de la prédiction.

## 4. Features

Les paramètres bruts disponibles sont conservés dans le contrat de préparation,
mais la première version du détecteur utilise uniquement les volatilités
causales sur une fenêtre de 20 cycles :

- `cycle_time_s_volatility_20` ;
- `injection_time_s_volatility_20` ;
- `cooling_time_s_volatility_20` ;
- `peak_pressure_bar_volatility_20` ;
- `clamp_force_kn_volatility_20` ;
- `mold_temperature_c_volatility_20` ;
- `barrel_temp_zone2_c_volatility_20` ;
- `energy_kwh_volatility_20`.

La volatilité d'un cycle est calculée avec les valeurs disponibles jusqu'à ce
cycle. Elle décrit une instabilité de trajectoire plutôt qu'un dépassement
statique de seuil.

La machine est traitée comme un contexte : un modèle normal est entraîné par
`machine_erp_ref`. Un modèle global sert de repli pour une machine inconnue.

## 5. Modèle et protocole

- algorithme : `sklearn.ensemble.IsolationForest` ;
- 200 arbres ;
- seed reproductible `42` ;
- imputation médiane puis standardisation ;
- entraînement sur les cycles historiques avec `scrap_flag = 0` ;
- seuil d'alerte au 98e percentile des scores de la population normale ;
- split temporel 2/3–1/3 **à l'intérieur de chaque machine** ;
- aucune lecture de la vérité terrain d'évaluation.

La raison de ne pas utiliser une régression logistique comme modèle principal
est expérimentale : les données synthétiques changent de régime entre les
machines et la régression obtenait un classement inférieur au hasard sur le
label futur. Le détecteur d'anomalies est mieux aligné avec la question
« comportement inhabituel » et obtient un signal de classement plus utile,
sans le présenter comme une causalité.

## 6. Contrat de sortie

Une prédiction produite par `ml.process_drift.predict` contient :

```json
{
  "anomaly_score": 0.73,
  "predicted_instability_next_20_cycles": true,
  "threshold": 0.41,
  "horizon_cycles": 20,
  "model_version": "hdt-process-drift-iforest-v1"
}
```

`anomaly_score` n'est pas une probabilité calibrée. L'explication doit être
produite séparément en affichant les volatilités contributrices, puis vérifiée
par `DeterministicInvestigator` avec les preuves machine.

## 7. Artefacts et reproductibilité

- Code : `ml/process_drift.py` ;
- entraînement : `scripts/train_process_drift.py` ;
- tests : `tests/test_process_drift.py` ;
- artefact : `models/process_drift_hdt_v1.joblib` ;
- métadonnées : `models/process_drift_hdt_v1.meta.json`.

La metadata conserve la version, le contrat de features, la cible, l'horizon,
la fenêtre, le protocole de split, les métriques et la déclaration
`ground_truth_used: false`.

## 8. Limites et validation terrain à prévoir

Le modèle est un **prototype offline sur données synthétiques**.

Il ne permet pas encore de conclure que :

- l'alerte détecte une cause physique donnée ;
- le score est calibré comme une probabilité ;
- une réduction de rebut est obtenue en production ;
- un seuil de 98 % est universel ;
- les performances se généralisent à une autre matière, recette, moule ou
  machine.

Pour une validation industrielle, il faut ajouter :

- les tolérances versionnées par machine + recette ;
- les identifiants moule, matière et cavité ;
- les mesures de masse, cotes, warpage et aspect horodatées ;
- les débits/températures aller-retour du refroidissement ;
- les événements de maintenance avec cause et validation ;
- un split par période, OF et changement de recette ;
- une mesure du délai d'anticipation et des fausses alertes par OF.

## 9. Mapping compétences DEVIA

| Compétence | Preuve apportée par HDT | Niveau honnête |
|---|---|---|
| C6 | Veille EUROMAP, articles, HAL et NIST dans `source-plasturgie/` | Défendable |
| C7 | Reformulation du problème : dérive future plutôt que contrôle hors tolérance | Défendable |
| C8 | Choix argumenté d'un détecteur explicable et comparaison avec le baseline rebut | Partielle à consolider |
| C9 | Contrat de features, cible future et séparation entraînement/inférence | Défendable sur le périmètre offline |
| C10 | Pipeline sklearn versionné, script reproductible et artefact joblib | Défendable offline |
| C11 | Features temporelles causales et modèle contextualisé par machine | Défendable prototype |
| C12 | Split temporel, AP, ROC-AUC, lift, précision, rappel et taux d'alerte | Défendable avec limites synthétiques |
| C13 | Package `joblib`, metadata, tests de contrat et smoke test de prédiction | Défendable pilote ; intégration runtime à compléter |

Formulation orale recommandée :

> « Les tolérances restent contrôlées par des règles déterministes. HDT ajoute
> une détection de trajectoire : il apprend le comportement normal de chaque
> machine et signale une volatilité multivariée inhabituelle avant une séquence
> instable. Le score est une priorité d'inspection ; le moteur déterministe
> fournit ensuite l'explication et les preuves. Le modèle reste à valider sur
> des données terrain. »
