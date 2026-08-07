# Mise à jour des preuves de certification — pivot HDT

Ce document fournit des blocs prêts à intégrer dans :

- `docs/certification/oral/E2-veille-IA-C6-C8.md` ;
- `docs/certification/oral/E3-service-IA-C9-C13.md` ;
- `docs/certification/coverage-matrix.md`.

Il remplace le cadrage où le risque de rebut est le sujet ML principal. Le cadrage à retenir est : **règles de tolérance, détecteur HDT contextualisé par machine, puis `DeterministicInvestigator` pour l'explication et les preuves**.

## 1. Message de référence commun

Le besoin n'est pas de remplacer une tolérance industrielle par une boîte noire. Une valeur hors tolérance doit rester traitée par une règle déterministe issue de la fiche de réglage versionnée. Le besoin complémentaire est de repérer une trajectoire qui devient instable alors que les valeurs individuelles sont encore acceptables.

**HDT** signifie *Horizon de dérive sous tolérance*. Le détecteur observe la volatilité multivariée récente d'une machine et donne une priorité d'inspection. Il ne commande pas la presse, ne déclenche pas un arrêt et ne modifie pas automatiquement un réglage. Le `DeterministicInvestigator` reprend ensuite le contexte machine, les baselines et les mesures disponibles pour produire des hypothèses, des preuves, des contradictions et une prochaine vérification.

La séparation des responsabilités est donc :

1. **Règles de tolérance** : décision autoritaire sur le hors-tolérance connu ;
2. **HDT Isolation Forest** : détection/priorisation d'une trajectoire inhabituelle sous tolérance ;
3. **`DeterministicInvestigator`** : explication locale, preuves traçables et validation humaine.

HDT est actuellement un **prototype évalué sur des données synthétiques**. Son endpoint sécurisé `/api/v1/process-drift` et son panneau UI sont maintenant intégrés, mais l'écran atelier s'abstient tant qu'une fenêtre de cycles bruts n'est pas disponible. Il n'est pas présenté comme validé terrain ni calibré comme une probabilité.

## 2. Bloc prêt à intégrer dans E2 — besoin, veille et benchmark

### Message central E2

> Le pilote sépare le contrôle connu de l'exploration de dérive. Les règles de tolérance restent la référence pour dire qu'un paramètre est hors plage. HDT ajoute une détection de trajectoire : une Isolation Forest apprend le comportement normal de chaque machine et signale une volatilité multivariée inhabituelle, même si chaque valeur prise isolément reste acceptable. Le `DeterministicInvestigator` ne remplace pas ce score : il l'explique avec des preuves machine et laisse la décision à un humain.

### Besoin à présenter

Une fiche de réglage peut contrôler une excursion simple, mais elle ne décrit pas toujours l'augmentation conjointe de la variabilité du temps de cycle, de la pression, du refroidissement, de la température du moule ou de l'énergie. L'objectif est donc de répondre à :

> « La trajectoire récente de cette machine est-elle suffisamment inhabituelle pour justifier une inspection avant une séquence qualité instable ? »

Le système doit rester local, explicable, on-premise et réversible. Une alerte HDT est une **priorité d'inspection**, jamais une cause physique démontrée.

### Veille mobilisable

La veille plasturgie disponible dans `source-plasturgie/veille-index/` justifie une lecture prudente des signaux : température, pression, refroidissement, temps de cycle, énergie et force de fermeture dépendent de la matière, de la géométrie, du moule, des capteurs et de la machine. Les sources EUROMAP 77/83 servent surtout à l'interopérabilité et au vocabulaire des données, pas à fournir des seuils universels. Les revues et articles locaux confirment l'intérêt du monitoring et des profils process, mais leurs résultats ne sont pas des performances IDDRV transférables.

La décision de veille est donc de versionner le contrat de données, les tolérances par contexte, le split temporel, les métriques, le seuil d'alerte et la validation humaine. Les références effectivement vérifiées et leurs limites sont consignées dans `source-plasturgie/veille-index/journal-veille.md` et `feature-to-defect-matrix.md`.

### Benchmark : règles, SPC et ML

| Approche | Ce qu'elle apporte | Limite | Décision IDDRV |
|---|---|---|---|
| Règles de tolérance | Décision immédiate, locale, auditable et explicable sur un dépassement connu | Détecte mal une dérive conjointe tant que chaque variable reste dans sa plage | Référence autoritaire et fallback |
| SPC | Détection de décalage, tendance et dispersion avec une baseline statistique | Demande un procédé suffisamment stable, des limites validées et un réglage par contexte | Complément à instrumenter et à valider avec le responsable process |
| ML supervisé, par exemple `rebut-risk` | Score de classification si des labels qualité fiables existent | Dépend des labels, du déséquilibre et des changements de machine ; risque de fuite ou de mauvaise généralisation | Baseline historique, pas sujet principal |
| ML anomalie HDT | Détecte une trajectoire multivariée inhabituelle avec peu de labels et un modèle normal par machine | Score non calibré ; seuil et généralisation restent à valider | Prototype retenu pour prioriser l'inspection |

Le benchmark ne prétend pas avoir établi une performance SPC ou règles contre HDT : aucune métrique comparative de terrain n'est disponible. La comparaison actuelle est une décision d'architecture et une évaluation offline du prototype. La régression logistique de rebut reste conservée comme baseline historique ; sur le jeu synthétique, elle classe moins bien que le détecteur d'anomalie pour la cible future et n'est donc pas le modèle principal.

### Paramétrage du prototype HDT

- algorithme : `sklearn.ensemble.IsolationForest` ;
- 200 arbres, `random_state=42` ;
- imputation médiane puis standardisation ;
- un modèle normal par `machine_erp_ref`, avec modèle global de repli pour une machine inconnue ;
- entraînement sur les cycles historiques `scrap_flag = 0` ;
- seuil par machine au 98e percentile des scores de la population normale ;
- score d'anomalie de classement, **pas une probabilité calibrée**.

### Cible proxy actuelle

L'unité est le cycle et l'horizon est de 20 cycles. La colonne cible est `instability_next_20_cycles`. Pour mesurer le prototype avec les données disponibles, la cible offline vaut 1 si au moins trois `scrap_flag` apparaissent dans les 20 cycles futurs. Le cycle courant et son passé servent aux features ; le futur ne sert qu'à construire cette cible.

Ce label est un **proxy synthétique de séquence instable**, pas une vérité industrielle universelle. Il devra être remplacé par un événement validé : excursion hors tolérance persistante pendant `k` cycles, alarme SPC validée, dérive qualité mesurée ou intervention opérateur qualifiée.

### Features et prévention des fuites

La première version utilise uniquement des volatilités causales sur une fenêtre de 20 cycles :

- `cycle_time_s_volatility_20` ;
- `injection_time_s_volatility_20` ;
- `cooling_time_s_volatility_20` ;
- `peak_pressure_bar_volatility_20` ;
- `clamp_force_kn_volatility_20` ;
- `mold_temperature_c_volatility_20` ;
- `barrel_temp_zone2_c_volatility_20` ;
- `energy_kwh_volatility_20`.

La volatilité est calculée avec les valeurs disponibles jusqu'au cycle observé. `machine_erp_ref` est un contexte de sélection du modèle, pas une preuve de défaut. `ground_truth.json`, `quality_flag`, `defect_type` et toute mesure qualité postérieure ne sont pas utilisés comme features. `scrap_flag` sert uniquement offline à construire le proxy futur et à sélectionner la population normale ; il n'est jamais fourni au modèle à l'inférence.

### Split et métriques actuelles

Le split est temporel, deux tiers pour l'entraînement et un tiers pour le test, **à l'intérieur de chaque machine**. La référence exécutée contient 25 461 lignes d'entraînement, 12 732 lignes de test, 601 événements proxy train et 156 événements proxy test.

Résultats du holdout synthétique :

| Métrique | Résultat |
|---|---:|
| Average precision | **14,07 %** |
| Prévalence de référence | **1,23 %** |
| Lift vs prévalence | **11,48×** |
| ROC-AUC | **0,878** |
| Precision au seuil machine | **12,29 %** |
| Recall au seuil machine | **23,72 %** |
| Taux d'alerte | **2,36 %** — 301 / 12 732 |

Lecture correcte : le classement est meilleur que l'aléatoire sur ce holdout et le seuil signale environ 2,4 % des cycles. 14,07 % est une average precision, pas la probabilité d'une alerte ; 12,29 % et 23,72 % ne sont pas des garanties pour une usine réelle.

### Limites à dire explicitement

- Les données et la cible sont synthétiques ; le proxy futur `scrap_flag` ne remplace pas une mesure qualité ou une alarme SPC validée.
- Le score n'est ni causal ni calibré ; le percentile 98 n'est pas universel.
- La généralisation à une autre matière, recette, moule, cavité, machine ou capteur n'est pas démontrée.
- Il manque notamment des tolérances versionnées, des mesures de masse/cotes/warpage/aspect, les débits de refroidissement et des événements maintenance qualifiés.
- Il reste à mesurer le délai d'anticipation, les fausses alertes par OF, les changements de recette et l'abstention hors domaine.
- Le modèle ne déclenche aucune action automatique et ne doit pas être décrit comme validé terrain.

## 3. Bloc prêt à intégrer dans E3 — intégration et mise en service

### Architecture et responsabilité runtime

Le chemin opérationnel reste déterministe et fondé sur des preuves. Les règles de tolérance contrôlent les excursions connues. Le `DeterministicInvestigator` sélectionne une baseline, calcule les écarts et produit au maximum trois hypothèses avec preuves, contradictions, données manquantes et prochaine vérification. HDT est exposé par `/api/v1/process-drift` et possède un panneau UI, mais l'interface ne fabrique pas de cycles bruts à partir d'une timeline agrégée : elle affiche l'absence de données jusqu'à raccordement d'une source cycle.

Une sortie HDT contient notamment `anomaly_score`, l'alerte booléenne, le seuil, l'horizon et `model_version`. Le score est ensuite confronté aux preuves machine par l'investigateur déterministe. Une alerte HDT ne constitue donc pas une explication et ne remplace pas les règles ni les preuves persistées.

### Évaluation et séparation des données

L'entraînement et l'évaluation lisent uniquement les fichiers `machine_cycles_*.csv`. `data/scenarios/industrial_demo/ground_truth.json` est réservé à l'évaluation et n'est jamais lu par le runtime, les prompts, les conteneurs, les tables ou les API. Le contrat de données doit conserver cette propriété lors d'une future intégration.

Les métriques HDT sont celles du holdout synthétique indiqué en E2. Elles ne remplacent pas l'évaluation du `DeterministicInvestigator` sur ses scénarios : les deux preuves doivent rester séparées, car elles mesurent des objets différents. La prochaine validation doit utiliser un export industriel, un événement qualité validé, un split par période/OF/changement de recette et une revue humaine des alertes.

### Packaging et mise en service

Le code reproductible est `ml/process_drift.py`, l'entraînement est lancé par `scripts/train_process_drift.py`, et les artefacts sont `models/process_drift_hdt_v1.joblib` et `models/process_drift_hdt_v1.meta.json`. La metadata conserve le contrat de features, la cible proxy, le split, les métriques et `ground_truth_used: false`.

La mise en service doit ajouter une validation du schéma d'entrée, un contrôle de machine inconnue via le modèle global de repli, la journalisation de la version, la surveillance du taux d'alerte et une possibilité d'abstention. Tant que ces éléments et les données terrain ne sont pas qualifiés, le statut à présenter est **prototype offline**, pas modèle validé ni commande automatique.

## 4. Bloc prêt à intégrer dans `coverage-matrix.md` — C6 à C13

Les lignes suivantes remplacent le cadrage « modèle de risque de rebut » pour le bloc IA. Les statuts restent volontairement proportionnés aux preuves disponibles.

### C6 — Organiser et réaliser une veille technique et réglementaire

**Preuve fichier :** `source-plasturgie/veille-index/journal-veille.md`, `source-plasturgie/veille-index/feature-to-defect-matrix.md`, `source-plasturgie/euromap/EUROMAP102_reference.md`, `ml/HDT-process-drift.md`, `ml/VALIDATION-HDT.md`.

**Détail :** veille EUROMAP, NIST, scikit-learn et publications injection plastique ; séparation documentée entre tolérance, SPC, anomalie ML et explication déterministe ; limites de transférabilité et besoin de validation terrain explicités.

**Statut honnête :** **Défendable** — veille et recommandation documentées ; les seuils industriels et la vérité terrain restent à obtenir du site.

### C7 — Identifier des services d'IA préexistants

**Preuve fichier :** `ml/HDT-process-drift.md`, `ml/rebut_risk.py`, `ml/process_drift.py`, `source-plasturgie/veille-index/journal-veille.md`.

**Détail :** benchmark règles de tolérance / SPC / ML. Les règles restent le contrôle autoritaire ; SPC est le complément statistique à valider ; la régression de rebut est une baseline historique ; l'Isolation Forest HDT est retenue pour la détection de trajectoire inhabituelle par machine. Aucun LLM cloud ou RAG n'est présenté comme actif.

**Statut honnête :** **Défendable sur le benchmark et le prototype offline**.

### C8 — Paramétrer un service d'IA suivant sa documentation technique

**Preuve fichier :** `ml/process_drift.py`, `ml/HDT-process-drift.md`, `ml/VALIDATION-HDT.md`.

**Détail :** Isolation Forest scikit-learn versionnée, 200 arbres, seed 42, imputation médiane, standardisation, features causales sur 20 cycles, modèle par `machine_erp_ref`, repli global et seuil au 98e percentile. Le score est expliqué séparément par le `DeterministicInvestigator` et n'est pas une probabilité.

**Statut honnête :** **Défendable comme paramétrage offline** ; intégration runtime et calibration terrain non prouvées.

### C9 — Développer une API REST exposant un modèle d'IA

**Preuve actuelle :** `backend/app/api/incidents.py`, `backend/app/api/investigations.py`, `backend/app/diagnostics/engine.py` et les contrats/tests API exposent le diagnostic déterministe et ses preuves.

**Détail à ajouter :** ne pas dire que l'API expose déjà HDT. Elle expose le `DeterministicInvestigator` actif ; HDT reste un artefact prototype offline jusqu'à validation du contrat d'inférence, de la persistance du score et de la gestion des erreurs.

**Statut honnête :** **Prouvé pour le service déterministe ; API HDT prouvée, monitoring métier encore partiel**.

### C10 — Intégrer l'API d'un modèle ou service d'IA dans une application

**Preuve actuelle :** `frontend/src/lib/api.ts`, `frontend/src/pages/IncidentDetailPage.tsx` et les tests frontend montrent le parcours investigation → hypothèses → preuves → feedback du `DeterministicInvestigator`.

**Détail à ajouter :** le frontend ne doit pas présenter le score HDT comme une prédiction terrain avant intégration qualifiée. Une future intégration devra afficher version, seuil, contexte machine, statut prototype et preuves déterministes associées.

**Statut honnête :** **Prouvé pour le diagnostic déterministe ; panneau HDT intégré, raccordement des cycles bruts restant à faire**.

### C11 — Monitorer un modèle d'IA

**Preuve fichier :** `ml/VALIDATION-HDT.md`, `backend/app/diagnostics/engine.py`, les endpoints de feedback et les tests d'évaluation du diagnostic.

**Détail à ajouter :** suivre average precision, ROC-AUC, précision, rappel, prévalence, lift et taux d'alerte sur des fenêtres temporelles ; comparer la prévalence et les features par machine ; surveiller les machines inconnues, les valeurs manquantes, le drift et les alertes sans confirmation humaine. Les métriques 14,07 %, 0,878, 12,29 %, 23,72 % et 2,36 % sont une référence offline synthétique, pas un SLO terrain.

**Statut honnête :** **Partiel** — métriques et feedback existent ; monitoring continu, drift et validation terrain HDT restent à construire.

### C12 — Programmer les tests automatisés d'un modèle d'IA

**Preuve fichier :** `tests/test_process_drift.py`, `tests/test_rebut_risk.py`, `ml/process_drift.py`, `ml/VALIDATION-HDT.md`.

**Détail :** tester le contrat de features, les features causales, le split temporel par machine, l'absence de lecture de `ground_truth.json`, le modèle de repli machine inconnue, le format de sortie et la reproductibilité. Le test de performance doit conserver la séparation temporelle et signaler explicitement la nature synthétique du proxy.

**Statut honnête :** **Défendable offline** — tests du pipeline et métriques de référence ; pas de validation de performance terrain.

### C13 — Créer une chaîne de livraison continue d'un modèle d'IA

**Preuve fichier :** `scripts/train_process_drift.py`, `models/process_drift_hdt_v1.meta.json` lorsqu'il est produit, les workflows CI et les Dockerfiles existants.

**Détail :** versionner le code, le contrat de features, la metadata et les métriques ; produire l'artefact joblib ; vérifier un smoke test de chargement et de prédiction ; ne promouvoir qu'un artefact dont la provenance et le statut de validation sont lisibles. La livraison on-premise actuelle concerne le pilote déterministe ; HDT ne doit pas être déclaré déployé comme modèle validé.

**Statut honnête :** **Défendable pour le packaging reproductible offline ; intégration et promotion runtime HDT à compléter**.

## 5. Formulations orales prêtes à utiliser

### Réponse courte (E2)

> « Je ne remplace pas les tolérances par du ML. Une règle reste autoritaire lorsqu'une valeur sort de sa plage. HDT regarde la trajectoire des vingt derniers cycles et repère, par machine, une volatilité multivariée inhabituelle avec une Isolation Forest. Il donne une priorité d'inspection. Ensuite le `DeterministicInvestigator` fournit les preuves et l'humain décide. Les scores présentés viennent d'un holdout synthétique ; le modèle n'est pas validé terrain. »

### Réponse courte (E3)

> « Le service actuellement intégré expose le diagnostic déterministe, ses hypothèses, ses preuves et le feedback. HDT est un artefact offline versionné avec un contrat de features, un split temporel et des métriques ; je ne le présente pas comme déjà branché à l'API ni comme une commande machine. Avant promotion, il faut un vrai événement qualité, le monitoring du drift, l'abstention et une validation humaine. »

### Si l'on demande pourquoi pas seulement le rebut

> « Le rebut courant arrive après le cycle et dépend d'un proxy de qualité. Le sujet HDT est en amont : détecter une trajectoire qui devient instable avant la séquence. Le rebut-risk reste une baseline de comparaison, mais il ne porte plus le cadrage principal. »

### Si l'on demande ce que signifie 14,07 %

> « C'est l'average precision du holdout synthétique, à comparer à une prévalence de 1,23 %, soit un lift de 11,48 fois. Ce n'est pas une probabilité calibrée et cela ne garantit pas 14 % de précision sur le terrain. »

### Si l'on demande si le runtime lit la vérité terrain

> « Non. Le runtime et le pipeline ne lisent pas `ground_truth.json`. Il est réservé à l'évaluation. Le proxy offline est construit à partir des CSV de cycles, et la future validation devra remplacer ce proxy par un événement qualité validé. »

## 6. Références techniques internes

- `ml/HDT-process-drift.md` : définition, contrat, protocole et limites ;
- `ml/VALIDATION-HDT.md` : exécution de référence et métriques ;
- `ml/process_drift.py` : features, split, entraînement et prédiction ;
- `ml/README.md` : statut prototype et commandes ;
- `source-plasturgie/veille-index/journal-veille.md` : veille et décisions ;
- `source-plasturgie/veille-index/feature-to-defect-matrix.md` : hypothèses process prudentes.
