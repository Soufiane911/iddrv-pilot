# Modèles IDDRV

## `rebut_risk_v1`

Baseline de régression logistique scikit-learn pour estimer le risque de rebut
à partir des paramètres de cycle et de l'historique causal des 20 cycles
précédents.

Entraînement reproductible :

```bash
python scripts/train_rebut_risk.py
```

Contrat :

- label : `scrap_flag` (`0` / `1`) ;
- split chronologique : 2/3 train, 1/3 holdout final ;
- déséquilibre : `class_weight=balanced` ;
- aucune utilisation du fichier d'évaluation réservé au runtime ;
- `quality_flag`, `defect_type`, `part_quality_status` et le label courant sont
  exclus des features pour éviter la fuite de cible ;
- les features `previous_scrap_flag` et `rolling_scrap_rate_20` ne regardent que
  les cycles déjà terminés.

Résultats du holdout du 2025-02-14T15:21:49Z au 2025-02-17T02:12:34Z :

- 12 771 cycles, 207 rebuts ;
- prévalence de référence : 1,62 % ;
- average precision : 8,04 % ;
- lift contre la prévalence : 4,96× ;
- ROC-AUC : 0,593 ;
- precision rebut au seuil 0,5 : 3,17 % ;
- recall rebut au seuil 0,5 : 30,9 %.

Ces résultats démontrent un artefact ML évalué, mais ne constituent pas une
validation terrain ni une mise en production. Le moteur déterministe reste le
service d'investigation explicable du pilote.
