# Périmètre ML IDDRV

Ce dossier contient les modèles tabulaires reproductibles du pilote IDDRV. Le
ML ne remplace pas les règles de réglage ni le moteur explicable
`DeterministicInvestigator` : il sert à prioriser une alerte ou une inspection.

## Modèles

| Modèle | Rôle | Statut |
|---|---|---|
| `rebut_risk_v1` | Baseline de classification du rebut du cycle courant | Évalué, mais faible ; conservé comme comparaison |
| `hdt-process-drift-iforest-v1` | Détection contextualisée d'une trajectoire instable avant l'événement | Prototype offline évalué sur données synthétiques |

Le modèle HDT signifie **Horizon de dérive sous tolérance**. Il apprend le
comportement normal de chaque machine à partir des cycles historiques sans
rebut, puis calcule un score d'anomalie multivarié. Il ne doit pas être présenté
comme validé en production.

## Exécuter l'entraînement

```bash
python scripts/train_process_drift.py
```

Sorties :

```text
models/process_drift_hdt_v1.joblib
models/process_drift_hdt_v1.meta.json
```

Le script ne lit jamais `data/scenarios/**/ground_truth.json`.

## Vérification

```bash
python -m pytest -q tests/test_process_drift.py
python -m pytest -q tests/test_rebut_risk.py tests/test_process_drift.py
```

## Notes de certification

- `HDT-process-drift.md` décrit le besoin, le label, les features, le protocole,
  les limites et le mapping vers les compétences C6–C13.
- `VALIDATION-HDT.md` conserve les résultats de la dernière exécution et les
  conclusions honnêtes.
- Le détail de la veille plasturgie et des sources est dans
  `source-plasturgie/`.
