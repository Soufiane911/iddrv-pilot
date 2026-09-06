# Alignement du dépôt avec le rapport HDT

Ce document établit la traçabilité entre le rapport remis le **20 août 2026** et
les éléments reproductibles de cette release. `ab14852fb5f8e5771ee501066cac8ef2a7089870`
est la base historique du worktree. Les corrections HDT ont été vérifiées dans
la branche source `codex/report-alignment-2026-08-20` (commit `991ad30`) puis
portées dans cette release dédiée par édition de fichiers et validation locale.
La release candidate sera référencée par le tag `iddrv-report-10.98`.
L'artefact publié est celui vérifié sous Python 3.13.9, scikit-learn 1.7.2 et
joblib 1.5.2.

## Correspondance affirmation → preuve

| Affirmation du rapport | Preuve versionnée et vérifiable |
| --- | --- |
| Le pipeline apprend un détecteur HDT de dérive par machine | `ml/process_drift.py` : préparation causale, Isolation Forest contextualisée par machine et prédiction versionnée |
| Les entrées sont les cycles machine bruts | `ml/process_drift.py:load_cycle_files` lit uniquement `machine_cycles_*.csv`; `ground_truth.json` n'est pas lu |
| 38 313 cycles bruts donnent 38 253 lignes exploitables | `tests/test_process_drift.py` et la sortie JSON de `scripts/train_process_drift.py` |
| Le découpage temporel est 2/3–1/3 par machine | `ml/process_drift.py:temporal_split` et `time_boundary.per_machine` dans `models/process_drift_hdt_v1.meta.json` |
| Le jeu d'entraînement/test contient 25 500/12 753 lignes et 601/156 événements | `models/process_drift_hdt_v1.meta.json:rows` et sortie CLI |
| Les métriques du rapport sont AP 10,98 %, lift 8,97× et ROC-AUC 0,868 | `models/process_drift_hdt_v1.meta.json:metrics`, avec les valeurs flottantes exactes conservées |
| L'artefact utilisé pour le rapport est publiable | `models/process_drift_hdt_v1.joblib`, SHA-256 `29dea3dca96ad0e3bfa1b1e54a4f7e55bd0d351a61cbe209ab84962530424eb6` |
| L'environnement d'exécution est connu | `models/process_drift_hdt_v1.meta.json:environment` : Python `3.13.9`, scikit-learn `1.7.2`, joblib `1.5.2` |

## Reproduction exacte

Depuis la racine du dépôt, avec l'environnement `.venv-report` :

```bash
python3.13 --version                         # Python 3.13.9 attendu
python3.13 -m venv .venv-report
.venv-report/bin/python -m pip install --upgrade pip
.venv-report/bin/python -m pip install \
  "scikit-learn==1.7.2" "joblib==1.5.2"
.venv-report/bin/python -m pip install -r requirements.txt
```

Le runtime utilisé pour la publication doit confirmer les versions épinglées :

```bash
.venv-report/bin/python --version
.venv-report/bin/python -c \
  'import joblib, sklearn; print(sklearn.__version__, joblib.__version__)'
```

```bash
.venv-report/bin/python scripts/train_process_drift.py \
  --data-dir data/scenarios/industrial_demo \
  --artifact /tmp/report-alignment-hdt.joblib \
  --metadata /tmp/report-alignment-hdt.meta.json
```

La commande retourne `0` et imprime un objet JSON contenant `model_version`,
les chemins, les volumes, les événements, les métriques et les bornes temporelles.
Pour préserver l'artefact exact remis avec le rapport, la vérification de
reproductibilité doit écrire dans un répertoire temporaire :

```bash
TMP_REPORT_DIR=$(mktemp -d /tmp/report-alignment-regenerated.XXXXXX)
.venv-report/bin/python scripts/train_process_drift.py \
  --data-dir data/scenarios/industrial_demo \
  --artifact "$TMP_REPORT_DIR/process_drift_hdt_v1.joblib" \
  --metadata "$TMP_REPORT_DIR/process_drift_hdt_v1.meta.json"
cmp "$TMP_REPORT_DIR/process_drift_hdt_v1.meta.json" \
  models/process_drift_hdt_v1.meta.json
```

La preuve complète, incluant les prédictions, alertes et seuils, est rejouable
ainsi après la régénération temporaire :

```bash
TMP_REPORT_DIR=$(mktemp -d /tmp/report-alignment-proof.XXXXXX)
.venv-report/bin/python scripts/train_process_drift.py \
  --data-dir data/scenarios/industrial_demo \
  --artifact "$TMP_REPORT_DIR/process_drift_hdt_v1.joblib" \
  --metadata "$TMP_REPORT_DIR/process_drift_hdt_v1.meta.json"
cmp "$TMP_REPORT_DIR/process_drift_hdt_v1.meta.json" \
  models/process_drift_hdt_v1.meta.json
.venv-report/bin/python - "$TMP_REPORT_DIR/process_drift_hdt_v1.joblib" <<'PY'
import sys
import warnings
from pathlib import Path

import pandas as pd
from sklearn.exceptions import InconsistentVersionWarning

from ml.process_drift import (
    load_artifact,
    load_cycle_files,
    predict,
    prepare_inference_frame,
)

regenerated_path = Path(sys.argv[1])
with warnings.catch_warnings():
    warnings.simplefilter("error", InconsistentVersionWarning)
    published = load_artifact(Path("models/process_drift_hdt_v1.joblib"))
    regenerated = load_artifact(regenerated_path)

# Préparer tout l'historique avant de sélectionner exactement 500 lignes.
history = prepare_inference_frame(
    load_cycle_files(Path("data/scenarios/industrial_demo"))
)
sample = history.head(500)
if len(sample) != 500:
    raise RuntimeError(f"expected 500 rows, got {len(sample)}")

published_predictions = predict(published, sample).reset_index(drop=True)
regenerated_predictions = predict(regenerated, sample).reset_index(drop=True)
columns = [
    "anomaly_score",
    "predicted_instability_next_20_cycles",
    "threshold",
]
pd.testing.assert_frame_equal(
    published_predictions[columns],
    regenerated_predictions[columns],
    check_exact=True,
)
print("predictions, alerts and thresholds identical on exactly 500 rows")
PY
```

Cette commande échoue avec un code non nul si une version incompatible est
signalée, si l'échantillon n'a pas exactement 500 lignes ou si l'une des trois
colonnes diffère.

La metadata régénérée est identique, SHA-256
`07f05b215212a3eee1a870f6f89c418e5299c2ef81862c085ebaafbaa52c5b92`. Le SHA du
joblib régénéré n'est pas une condition de réussite : la sérialisation joblib
peut varier. La comparaison sémantique effectuée sur 500 lignes de l'historique
complet a donné des prédictions et des alertes identiques entre l'artefact
publié et l'artefact régénéré. Le joblib temporaire avait le SHA
`9b0326056fd93e1fa36526744a1dcb2ac77ba9f4e27ae33b5c0cb68d50005e40`.

## Tests et périmètre

Commandes exécutées :

```bash
.venv-report/bin/python -m pytest -q \
  tests/test_process_drift.py tests/test_process_drift_monitoring.py
.venv-report/bin/python -m pytest -q --ignore=tests/e2e
```

Résultats de la release vérifiés localement : **23 tests ciblés réussis** et
**254 tests produit réussis** avec `python -m pytest -q --ignore=tests/e2e`.
Le compteur **211 tests** annoncé dans le rapport correspond à l'état historique
au moment du dépôt ; il ne doit pas être présenté comme le total de cette
release. Les tests du générateur PDF académique local ne font pas partie du
dépôt publiable.

Le générateur PDF local, les travaux REST, le simulateur, la migration 012, les
captures UI/API, les changements README/Compose/backend et les autres travaux
postérieurs à la remise du rapport sont explicitement hors périmètre de cet
alignement.

## Limites

Le résultat HDT est un proxy évalué sur le scénario industriel fourni. Aucune
validation terrain n'est revendiquée. Le feedback opérateur/qualité n'est pas
branché dans une boucle d'apprentissage ou de recalibrage. Aucun déploiement
pilote n'a été exécuté; les performances et le seuil doivent donc être
revalidés avant toute décision industrielle.
