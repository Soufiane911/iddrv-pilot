# Démonstration HDT — script technique détaillé

Ce script sert de préparation complète sur environ 5 minutes. La V6 réserve 4 minutes à la démonstration E3 : raccourcir les transitions et conserver le contrat, la réponse, le refus et le statut de preuve.

## Objectif et scénario

Scénario unique : la presse `machine_erp_ref=1003` produit normalement, puis la volatilité conjointe de la pression de pointe et du refroidissement augmente. HDT signale une trajectoire inhabituelle ; l'utilisateur peut ensuite consulter un incident déjà présent dans le scénario, s'il existe. HDT ne crée pas automatiquement cet incident. `DeterministicInvestigator` fournit ensuite les preuves déterministes et l'opérateur confirme ou rejette l'hypothèse.

Le jeu de démonstration est **synthétique**. HDT est un prototype offline : il priorise une inspection, il ne commande pas la presse et ne remplace pas les tolérances ni l'analyse humaine.

## Prérequis et préparation

- Docker/Compose, Python 3.13.x et les dépendances du projet installés.
- Depuis la racine du dépôt, un fichier `.env` local contenant au minimum `POSTGRES_PASSWORD`, `DOCKER_DATABASE_URL` et `SESSION_SECRET`.
- Services disponibles : PostgreSQL/TimescaleDB, API, worker et web.
- Un compte `analyst` ou `supervisor` pour lancer l'investigation et enregistrer le feedback.
- Navigateur sur `http://localhost:8080`.
- Ne pas utiliser ni afficher `ground_truth.json` : il est réservé à l'évaluation.

Préparer l'artefact si nécessaire (avant la présentation) :

```bash
.venv/bin/python scripts/train_process_drift.py \
  --artifact /tmp/process_drift_hdt_v1.joblib \
  --metadata /tmp/process_drift_hdt_v1.meta.json
.venv/bin/python -m pytest -q tests/test_process_drift.py
```

Réponse attendue : création de `/tmp/process_drift_hdt_v1.joblib` et de `/tmp/process_drift_hdt_v1.meta.json`, puis tests verts. Ces sorties temporaires servent à la vérification et ne remplacent pas l'artefact publié sous `models/`, chargé par défaut par l'API. Le pipeline lit les `machine_cycles_*.csv` et n'utilise pas la vérité terrain d'évaluation.

## Commandes de lancement

```bash
docker compose up -d timescaledb redis api worker web
curl -fsS http://localhost:8080/api/health
open http://localhost:8080
```

Réponse attendue pour la santé : HTTP 200 avec un statut de service sain. Dans l'UI, ouvrir l'atelier, sélectionner la presse liée à `ARBURG-1003`, puis utiliser le replay temporel.

## Déroulé minuté et phrases d'oral

### 0:00–0:45 — Situation normale

**Action écran :** afficher l'atelier à `2025-02-11T21:00:00Z`, sélectionner `1003`, puis montrer le replay et les indicateurs stables.

**À dire :**

> « Je commence par une période normale. HDT ne cherche pas un dépassement isolé : il apprend la volatilité habituelle de cette machine sur une fenêtre causale de 20 cycles. La pression, le refroidissement et les autres variables restent cohérents ; aucune inspection n'est prioritaire. »

**À montrer :** état stable, fenêtre de référence, absence d'alerte prioritaire.

### 0:45–1:45 — Apparition de la dérive

**Action écran :** avancer le replay vers la période de dérive, autour de `2025-02-11T23:21:00Z` puis `2025-02-12T00:05:00Z`. Montrer la hausse de dispersion des mesures de pression de pointe et de temps de refroidissement, sans prétendre qu'une valeur est nécessairement hors tolérance.

**À dire :**

> « La machine reste peut-être dans les tolérances instantanées, mais sa trajectoire devient plus volatile. C'est précisément la zone où HDT complète les règles métier : il détecte une instabilité multivariée avant de conclure à une cause. »

### 1:45–2:30 — Appel API `process-drift`

**Action terminal :** appeler le contrat de démonstration suivant avec les 20 derniers cycles de la machine. Remplacer `<TOKEN>` et `<PAYLOAD_20_CYCLES>` par les valeurs préparées dans le scénario ; ne jamais envoyer de données futures ni de `ground_truth.json`.

```bash
curl -sS -X POST http://localhost:8080/api/v1/process-drift \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '<PAYLOAD_20_CYCLES>' | jq
```

Réponse attendue : lire les valeurs retournées par l'artefact chargé. Ne pas recopier un score ou un seuil d'une autre machine ou d'une capture historique :

```json
{
  "anomaly_score": "<score retourné>",
  "predicted_instability_next_20_cycles": "<booléen retourné>",
  "threshold": "<seuil retourné>",
  "horizon_cycles": 20,
  "model_version": "hdt-process-drift-iforest-v1"
}
```

**À dire :**

> « Je compare le score retourné au seuil de cette machine : HDT recommande, le cas échéant, une inspection sur les 20 prochains cycles. `anomaly_score` est un score de classement, pas une probabilité calibrée. Il ne signifie donc pas un pourcentage de chance d'avoir un incident. »

**Point de vérification avant la séance :** la route `/api/v1/process-drift` est disponible dans la build actuelle, mais elle attend des cycles bruts et non des points de timeline agrégés. Si l'environnement ne dispose pas de cette fenêtre brute, exécuter le smoke test offline du modèle et annoncer explicitement cette limite.

### 2:30–3:15 — Affichage UI

**Action écran :** revenir dans l'atelier, avancer le replay jusqu'à l'alerte, puis afficher le panneau HDT et, si le scénario en contient un, ouvrir l'incident existant séparément. Afficher le badge de surveillance, la courbe pression/refroidissement et le lien vers l'impact qualité.

**À dire :**

> « L'interface transforme le score en décision lisible : machine sous surveillance, période concernée, variables contributrices et impact observé. L'alerte ne déclenche pas d'arrêt automatique ; elle donne au responsable process un ordre de vérification. »

**Réponse attendue :** le panneau affiche l'état HDT correspondant aux cycles bruts consultés ; un incident existant reste un objet séparé. Les éléments de preuve et la période sont visibles dans le détail de l'incident lorsqu'il est disponible.

### 3:15–4:15 — Vérification par `DeterministicInvestigator`

**Action écran :** dans le détail de l'incident, cliquer sur **Lancer l'investigation** (rôle `analyst`/`supervisor`). À défaut, utiliser l'identifiant d'incident affiché :

```bash
curl -sS -X POST \
  "http://localhost:8080/api/v1/incidents/<INCIDENT_ID>/investigations" \
  -H 'Authorization: Bearer <TOKEN>' | jq
```

Réponse attendue : HTTP 200 avec `run_id`, des `hypotheses` et des `evidence`. Les preuves doivent citer la machine, la fenêtre temporelle, la comparaison à une baseline et les observations disponibles ; une insuffisance de données doit produire une abstention explicite plutôt qu'une cause inventée.

**À dire :**

> « HDT a priorisé la trajectoire. Maintenant, le moteur déterministe vérifie avec des faits observables : baseline, dérive de zone thermique, qualité et contexte opérateur. Il ne transforme pas le score ML en explication causale ; il sépare le signal de triage de la preuve. »

### 4:15–5:00 — Feedback humain et conclusion

**Action écran :** sélectionner le verdict, par exemple `confirmed` si la vérification terrain confirme la dérive, ou `rejected` si elle ne la confirme pas, saisir un commentaire et envoyer.

```bash
curl -sS -X POST \
  "http://localhost:8080/api/v1/incidents/<INCIDENT_ID>/feedback" \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '{"verdict":"confirmed","comment":"Volatilité pression/refroidissement confirmée par contrôle opérateur."}' | jq
```

Réponse attendue : HTTP 201 avec `id`, `incident_id`, `verdict` et `comment`.

**À dire :**

> « La décision finale reste humaine. Le feedback est tracé pour fermer la boucle de qualification ; il ne déclenche pas une action machine automatique. HDT sert à regarder plus tôt au bon endroit, puis l'investigateur et l'opérateur décident avec les preuves. »

## Limites à dire explicitement

- Les données et le scénario sont synthétiques ; les résultats ne valent pas validation industrielle.
- `anomaly_score` n'est pas une probabilité calibrée et le seuil au 98e percentile n'est pas universel.
- Le label offline — au moins trois rebuts dans les 20 cycles futurs — est un proxy synthétique, pas une vérité process.
- Une alerte ne prouve ni une cause physique ni un rebut futur ; elle recommande une inspection.
- La généralisation à une autre machine, matière, recette, moule ou capteur reste à mesurer sur des exports terrain.
- Les tolérances, les règles déterministes et l'humain restent prioritaires ; aucune modification ni aucun arrêt automatique n'est commandé par HDT.

## Vérification finale avant présentation

```bash
curl -fsS http://localhost:8080/api/health
.venv/bin/python -m pytest -q tests/test_process_drift.py
# vérifier manuellement : UI accessible, replay normal → dérive, investigation et feedback
```

Si l'appel `process-drift` n'est pas disponible dans l'environnement, ne pas masquer ce fait : faire la démonstration offline du modèle, puis montrer l'UI et les routes d'investigation/feedback réellement disponibles.
