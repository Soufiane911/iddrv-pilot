# Livraison du modèle HDT : preuves locales et limites

## Contrat observé sur la release consolidée

Base inspectée : `01fcb4fa8daa8261ca34cf2e44171a4d7836af5b`.
Le modèle servi reste `models/process_drift_hdt_v1.joblib`, version
`hdt-process-drift-iforest-v1`. Aucun binaire remplacé.
SHA-256 réel : `29dea3dca96ad0e3bfa1b1e54a4f7e55bd0d351a61cbe209ab84962530424eb6`.
Le SHA historique `8480d0b075831042afecd38bfa125bbf82970636d502ed4cb1d65a9c0a8a7b7d`
ne correspond PAS à cette release. Le manifeste d'inventaire versionné conserve
cette divergence, sans inventer dataset, seed ou commit d'entraînement original.
Le sidecar indique Python 3.13.9, sklearn 1.7.2, joblib 1.5.2 ; le chargement
réel et les tests de compatibilité réussissent dans ces versions. L'ancien
constat sklearn 1.9.0 n'est donc pas reproduit sur cette base. Les requirements
release imposent déjà sklearn 1.7.2 et joblib 1.5.2 : aucun changement nécessaire.

## Exécution reproductible

Dans un environnement isolé Python 3.13 :

    python -m pip install -r backend/requirements.txt scikit-learn==1.7.2 joblib==1.5.2 pandas==2.3.3 numpy==2.2.6 pytest==8.4.2
    python -m pytest -q tests/test_process_drift.py tests/test_model_artifact_compatibility.py tests/test_training_scripts.py tests/test_model_delivery.py
    python scripts/package_process_drift.py --data-dir data/scenarios/industrial_demo --output /tmp/iddrv-candidate-unique

Choisir un dossier inexistant. Le script refuse `models/` et les sorties existantes.
Il réutilise le code release : chargement CSV, préparation causale, split temporel
par machine, entraînement Isolation Forest seed 42, évaluation, validation,
sauvegarde, vérification SHA puis chargement de son propre artefact et comparaison
exacte des inférences avant/après sérialisation. Le manifeste n'est écrit qu'après
succès ; un répertoire sans manifeste est incomplet et ne doit pas être promu.

Contrôles données : schéma requis, labels exactement 0/1, identifiants et dates
présents, dates converties et conservées en UTC, refus des NaT après conversion,
absence de doublons machine/instant UTC (y compris avec décalages horaires différents)
avant entraînement, et absence d'infinis ; les NaN
numériques partiels sont inventoriés et traités par l'imputation existante.
Une colonne numérique entièrement absente bloque la chaîne. Les métriques doivent
être finies et le lift AP/prévalence au moins 1. Ce seuil minimal est un garde-fou
offline, pas une acceptation métier. Les manifestes candidats enregistrent SHA des
CSV, artefact, sidecar et sources, révision Git, environnement, configuration,
seed, volumes manquants, métriques et résultat du smoke.

Avant toute lecture des fichiers puis désérialisation, la vérification du manifeste
package/servi exige exactement `process_drift_hdt_v1.joblib` et
`process_drift_hdt_v1.meta.json`, chacun avec un SHA-256 hexadécimal de 64 caractères.
Un manifeste vide, incomplet, avec nom inconnu ou hash mal formé est refusé.
La vérification des données utilise explicitement un contrat distinct acceptant
les noms variables `machine_cycles_*.csv`.

Tests : préparation/split/contrat existants, intégrité du modèle release,
manifestes invalides refusés avant désérialisation, doublons UTC et NaT refusés
avant entraînement,
altération de fichier et chemin interdit, deux entraînements donnant des
manifestes et SHA identiques dans le même environnement, train-load-inference,
refus d'écrasement. Pas de mesure de couverture ajoutée ou revendiquée.

## Déclencheur et livraison

`.github/workflows/model-delivery.yml` propose uniquement `workflow_dispatch` :
installation, tests, package candidat puis conservation de l'archive CI 7 jours.
Workflow non exécuté sur GitHub dans cette intervention ; aucun push ni livraison
distante réalisés. Aucun déploiement automatique, secret ou permission modifié.
L'archive locale n'est pas une preuve de déploiement. Une promotion exige revue du
manifeste, validation métier et procédure opérationnelle séparée. Le rollback
reste la conservation de l'artefact release inchangé, pas une opération effectuée.

## Vérification et portée certification

Exécution locale réelle sans installation : Python Anaconda 3.13.9, sklearn 1.7.2,
joblib 1.5.2, pandas 2.3.3, numpy 2.2.6 ; **28 tests réussis en 8,48 s**
après les corrections P2 (commande `python3 -m pytest -q` sur les quatre fichiers
ci-dessus). Le roundtrip exact et la reproductibilité restent vérifiés.
Aucun accès réseau/DB ou chargement d'artefact externe inconnu. Le venv du dépôt
principal (Python 3.14) n'avait pas sklearn ; il n'a pas été modifié.

C8 : contrat release inventorié et chargement vérifié ; pas de test endpoint ici.
C12 : intégrité, données et chaîne reproductible mieux couvertes.
C13 : chaîne manuelle déclenchable proposée, package local testé ; exécution
GitHub, promotion, préproduction et déploiement restent non démontrés.
Aucune compétence ni validation jury auto-attribuée.

Limites : le dataset industrial_demo est synthétique, le label un proxy de
rebuts futurs, pas une vérité terrain. Les expériences locales non suivies ne
sont ni importées ni assimilées au modèle servi. Le split existant ne purge pas
explicitement l'horizon futur à la frontière ; ses métriques ne démontrent pas
une validation temporelle indépendante. SHA assure l'intégrité relative à un
manifeste de confiance, pas l'authenticité ; le serveur n'applique pas ce nouveau
manifeste automatiquement. Les dépendances transitives ne sont pas entièrement
verrouillées, et la reproductibilité bit-à-bit inter-OS n'est pas revendiquée.
