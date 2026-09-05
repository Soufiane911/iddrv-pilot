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

L'environnement de référence est Python 3.13.x avec scikit-learn 1.7.2 et
joblib 1.5.2. Ces versions sont épinglées dans `requirements.txt` et
`backend/requirements.txt` pour éviter les avertissements de désérialisation
scikit-learn.

```bash
.venv/bin/python scripts/train_process_drift.py \
  --data-dir data/scenarios/industrial_demo \
  --artifact /tmp/process_drift_hdt_v1.joblib \
  --metadata /tmp/process_drift_hdt_v1.meta.json
.venv/bin/python scripts/train_rebut_risk.py \
  --data-dir data/scenarios/industrial_demo \
  --artifact /tmp/rebut_risk_v1.joblib \
  --metadata /tmp/rebut_risk_v1.meta.json
```

Les scripts refusent de remplacer une sortie existante sans `--force`. Ils
échouent si le répertoire ne contient pas de `machine_cycles_*.csv` et
n'utilisent jamais `data/scenarios/**/ground_truth.json`.

Les chargeurs vérifient la provenance embarquée dans les nouveaux artefacts
(et dans la metadata sœur pour les artefacts publiés antérieurs) : Python de la
même série majeure/mineure, `scikit-learn==1.7.2` et `joblib==1.5.2`. Un
`InconsistentVersionWarning`, une metadata sœur absente ou incohérente, et un
contrat de features invalide font échouer le chargement ; aucun avertissement
critique n'est ignoré. Les chemins par défaut sont ancrés
à la racine du dépôt afin de ne pas dépendre du répertoire courant. Un chemin
personnalisé peut être fourni via `PROCESS_DRIFT_MODEL_PATH` ou
`SCRAP_RISK_MODEL_PATH`.

Les sorties publiées sont :

```text
models/process_drift_hdt_v1.joblib
models/process_drift_hdt_v1.meta.json
models/rebut_risk_v1.joblib
models/rebut_risk_v1.meta.json
```

Le moniteur HDT conserve actuellement scores et feedback uniquement en mémoire
(et perd cet état au redémarrage) ; il ne constitue pas une persistance de
prédictions ni une boucle de réentraînement.

## Vérification

```bash
.venv/bin/python -m pytest -q tests/test_process_drift.py
.venv/bin/python -m pytest -q tests/test_rebut_risk.py tests/test_process_drift.py
```

Pour vérifier la compatibilité du binaire publié, charger les artefacts avec
`InconsistentVersionWarning` promu en erreur :

```bash
.venv/bin/python -W error::sklearn.exceptions.InconsistentVersionWarning -c \
  'from ml.process_drift import load_artifact; from pathlib import Path; load_artifact(Path("models/process_drift_hdt_v1.joblib"))'
```

## Notes de certification

- `HDT-process-drift.md` décrit le besoin, le label, les features, le protocole,
  les limites et le mapping vers les compétences C6–C13.
- `VALIDATION-HDT.md` conserve les résultats de la dernière exécution et les
  conclusions honnêtes.
- Les sources de veille plasturgie sont des artefacts externes, non embarqués
  dans ce checkout. Leur emplacement et leur commit de référence immuable
  sont consignés dans `ml/EXTERNAL-SOURCES.md`.
