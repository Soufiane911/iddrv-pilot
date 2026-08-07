# Rapport E2 — Veille et choix d'une solution d'IA

**Compétences :** C6 à C8 — **Pages cible :** 15–20 — **Statut :** brouillon rédigé (à relire, illustrer et finaliser)

---

## 1. Contexte et besoin (C6)

Le pilote IDDRV surveille des presses d'injection plastique (Arburg, Engel) via
le modèle canonique EUROMAP 77/83. Une **fiche de réglage versionnée** contrôle
chaque paramètre : lorsqu'une valeur sort de sa plage de tolérance, une règle
déterministe le signale immédiatement. Ce contrôle est **autorisé, local et
auditable** — il reste la référence pour les dépassements connus.

Mais une machine peut rester **dans les tolérances instantanées** alors que la
**variabilité conjointe** de ses paramètres augmente : temps de cycle, pression,
refroidissement, température de moule, énergie. Chaque valeur prise isolément
reste acceptable ; la trajectoire, elle, devient instable. Le besoin complémentaire
est donc de détecter cette trajectoire assez tôt pour **prioriser une inspection**,
avant qu'une séquence qualité instable ne produise des rebuts.

La question opérationnelle du pilote :

> « La trajectoire récente de cette machine est-elle suffisamment inhabituelle
> pour justifier une inspection avant une séquence instable ? »

Contraintes du projet : **on-premise**, confidentialité des données d'atelier,
explicabilité des alertes, reproductibilité des artefacts, et **aucune dépendance
LLM/RAG/OpenAI en production** pour ce pilote.

## 2. Méthodologie de veille (C6)

La veille est organisée comme un **journal traçable** : chaque entrée associe une
source à une question opérationnelle, une synthèse paraphrasée, son impact sur le
projet et une décision. Le statut de lecture est explicite, pour ne jamais
présenter une source « repérée » comme une source « consultée » :

- **lu — page** : page ouverte et contenu utile vérifié ;
- **lu — résumé** : résumé public et métadonnées vérifiés, pas le texte intégral ;
- **lu — contenu ciblé** : passages utiles vérifiés, pas une lecture exhaustive ;
- **à lire** : piste repérée, à ne pas présenter comme source consultée.

La date d'accès de toutes les entrées vérifiées est le **2026-08-03**. Le journal
complet se trouve dans `source-plasturgie/veille-index/journal-veille.md`
(entrées **S01 à S13**), et les hypothèses paramètre → défaut dans
`source-plasturgie/veille-index/feature-to-defect-matrix.md`.

### Sources vérifiées (synthèse)

| Source | Question | Apport pour IDDRV |
|---|---|---|
| **EUROMAP 77** (site officiel, page) | Relier données machine au MES | Vocabulaire canonique IMM–MES, base de types EUROMAP 83 ; pas de relation défaut-paramètre |
| **EUROMAP 83** (site officiel, page) | Cadre d'information multi-constructeur | Types généraux OPC UA pour machines plastiques ; repère de noms/interfaces, pas un référentiel de seuils |
| **NIST AI RMF + Playbook** (pages officielles) | Encadrer un score ML industriel | Cadre Govern/Map/Measure/Manage : contrat de données, métriques, seuil, abstention, suivi de dérive, validation humaine |
| **scikit-learn — LogisticRegression** (doc) | Baseline locale paramétrable | Compatible avec un score tabulaire léger, versionné, inspectable |
| **scikit-learn — ensembles** (doc) | Comparer arbres/boosting | Candidats du benchmark, uniquement avec séparation temporelle et métriques de rebut rare |
| **Zhao et al., 2022** (revue warpage/shrinkage, contenu ciblé) | Paramètres du gauchissement | Température moule/fusion, vitesses/pressions, maintien, refroidissement ; effets interactifs, pas de seuil transférable |
| **A Review on ML Models in Injection Molding, 2022** (résumé) | Familles ML utilisées | Qualité liée à vitesse/pression/moule ; souligne collecte, préparation, séparation et validation des données |
| **Intelligent Injection Molding, 2020** (résumé) | Place des capteurs et du contrôle | Séparer observer / prédire / agir ; pas d'action automatique sans validation |
| **Short-Shot Defects by Transfer Learning, 2023** (résumé) | Prédire un short shot | Réseau sur états process ; la simulation seule ne suffit pas ; non transférable tel quel à IDDRV |
| **Wear Resistance of Moulds (GFRP), 2017** (résumé) | Usure du moule | Fibres de verre → usure abrasive cavités/canaux ; covariable matière/charge/cycles à confirmer par métrologie |
| **Advanced Injection Molding Methods, 2023** (contenu ciblé) | Rôle température/pression/refroidissement | Effets dépendants de la matière et du procédé ; utiliser des écarts à la baseline, pas des valeurs universelles |
| **EUROMAP 101** (page repérée, **à lire**) | Structurer données moule | Piste usure/maintenance ; spécification non analysée, ne pas citer en détail |
| **Fiches matière / manuels constructeur** (**à lire**) | Seuils réels applicables | Limite critique : aucun grade de résine, manuel ou plan de moule du site n'a été vérifié |

### Enseignements de la veille

1. **Pas de seuil universel** : les effets dépendent de la matière, de la géométrie,
   de la cavité, du moule, des capteurs, de la recette et de la machine. Toute
   valeur absolue issue de la littérature est un **guide d'hypothèse**, pas une règle.
2. **Deux objets distincts** : la **dérive** (variation progressive d'un signal) et
   le **risque de rebut** (cible ML) ne se traitent pas avec le même outil.
3. **EUROMAP sert l'interopérabilité**, pas la causalité : les normes donnent un
   vocabulaire, pas des seuils qualité.
4. **Le ML industriel se juge sur les rebuts rares** : average precision, ROC-AUC,
   précision/rappel au seuil — pas l'accuracy.

## 3. Benchmark des approches (C7)

Le besoin est découpé en **deux fonctions** : expliquer un incident (avec preuves)
et **estimer le risque d'une trajectoire instable** à venir.

### 3.1 Comparatif

| Approche | Ce qu'elle apporte | Limite | Décision IDDRV |
|---|---|---|---|
| **Règles de tolérance** | Décision immédiate, locale, auditable, explicable sur un dépassement connu | Détecte mal une dérive conjointe tant que chaque variable reste dans sa plage | **Référence autoritaire et fallback** (déjà en production pilote) |
| **SPC / EWMA / CUSUM** | Détecte décalage, tendance et dispersion sur baseline statistique | Nécessite un procédé stable, des limites validées, un réglage par contexte | Complément à instrumenter avec le responsable process |
| **ML supervisé — régression logistique rebut** (`rebut-risk-logistic-v1`) | Score de classification si labels qualité fiables | Dépend des labels, du déséquilibre, des changements de machine ; risque de fuite temporelle | **Baseline historique conservée**, pas le sujet principal |
| **ML anomalie — Isolation Forest HDT** | Détecte une trajectoire multivariée inhabituelle avec peu de labels, modèle normal par machine | Score non calibré ; seuil et généralisation à valider | **Prototype retenu** pour prioriser l'inspection |
| **LLM / RAG cloud** | Synthèse documentaire possible | Confidentialité, coût, hallucination, corpus procédures absent, explicabilité faible pour un score | **Écarté pour le pilote** ; RAG différé tant qu'un corpus autorisé n'existe pas |

### 3.2 Éléments chiffrés de la comparaison

Sur le jeu synthétique du pilote, la baseline supervisée `rebut-risk-logistic-v1`
(prediction du rebut courant) atteint un ROC-AUC de **0,593** avec un lift de
**4,96×** — elle classe à peine mieux que le hasard lorsque la distribution des
scénarios et des machines change entre périodes. Elle reste conservée comme
baseline historique, mais ne porte pas le cadrage principal.

L'Isolation Forest HDT (détection de trajectoire instable future, §5) atteint un
ROC-AUC de **0,878** et un lift de **11,48×** sur le même type de découpage
temporel. La comparaison n'est pas une performance de terrain : c'est une
**décision d'architecture** appuyée par une évaluation offline du prototype.

### 3.3 Critères de choix

Les critères de benchmark retenus : qualité sur les rebuts rares (average
precision, ROC-AUC, précision/rappel au seuil), calibration, fuite temporelle,
explicabilité atelier, fonctionnement on-premise, coût/latence, robustesse aux
valeurs manquantes et maintenance. **Une précision globale seule est insuffisante**
lorsque le rebut est minoritaire.

## 4. Décision : le pivot HDT (C7)

Le cadrage retenu sépare trois responsabilités :

```text
Règles de tolérance (décision autoritaire)
        │
        ▼
HDT — Isolation Forest par machine (priorité d'inspection)
        │
        ▼
DeterministicInvestigator (hypothèses + preuves explicables)
        │
        ▼
Décision humaine
```

1. **Règles de tolérance** : le hors-tolérance connu reste traité par la fiche de
   réglage versionnée — autoritaire, sans ML.
2. **HDT** (*Horizon de dérive sous tolérance*) : une Isolation Forest apprend le
   comportement **normal de chaque machine** et signale une volatilité multivariée
   inhabituelle, **même si chaque valeur prise isolément reste acceptable**. Une
   alerte HDT est une **priorité d'inspection**, jamais une cause démontrée, et ne
   déclenche **aucune action automatique** sur la presse.
3. **`DeterministicInvestigator`** : reprend le contexte machine, les baselines et
   les mesures disponibles pour produire hypothèses, preuves, contradictions et
   prochaine vérification. L'humain décide.

Le **LLM/RAG est écarté** pour le pilote : les données sont des colonnes
numériques de cycle (pas de besoin de synthèse textuelle), la confidentialité et
le coût d'un cloud ne sont pas acceptables en l'état, le risque d'hallucination
est incompatible avec des alertes d'atelier, et aucun corpus de manuels/procédures
autorisé n'existe encore. L'interface `Investigator` (provider pattern) reste
prête à accueillir un agent plus tard, sous les gates définies par le projet.

## 5. Paramétrage du prototype (C8)

Le prototype est implémenté selon la documentation scikit-learn :

| Paramètre | Valeur |
|---|---|
| Algorithme | `sklearn.ensemble.IsolationForest` |
| Arbres | 200, `random_state=42` |
| Prétraitement | imputation médiane puis standardisation |
| Contextualisation | un modèle normal par `machine_erp_ref` + modèle global de repli |
| Population normale | cycles historiques `scrap_flag = 0` |
| Seuil | 98e percentile des scores de la population normale (par machine) |
| Fenêtre de volatilité | 20 cycles |
| Horizon d'anticipation | 20 cycles |

**Features** (volatilités causales sur la fenêtre, calculées jusqu'au cycle
observé uniquement) : temps de cycle, temps d'injection, refroidissement,
pression de pointe, force de fermeture, température de moule, température
fourreau zone 2, énergie — soit 8 volatilités + `machine_erp_ref` comme contexte
de sélection du modèle.

**Cible offline (proxy)** : `instability_next_20_cycles` vaut 1 si **au moins
trois rebuts** (`scrap_flag`) apparaissent dans les 20 cycles futurs. Le cycle
courant et son passé servent aux features ; le futur ne sert qu'à construire la
cible. C'est un **proxy synthétique de séquence instable**, pas une vérité
industrielle : il devra être remplacé par un événement validé (excursion SPC,
dérive qualité mesurée, intervention opérateur qualifiée).

**Prévention des fuites** : `ground_truth.json`, `quality_flag`, `defect_type`
et toute mesure qualité postérieure ne sont jamais utilisés comme features ;
`scrap_flag` ne sert qu'offline (proxy + population normale) et n'est jamais
fourni au modèle à l'inférence.

## 6. Évaluation du holdout (C8)

**Protocole** : split temporel **2/3 entraînement – 1/3 test à l'intérieur de
chaque machine** (jamais de split aléatoire). Référence exécutée le 2026-08-03 :
25 461 lignes d'entraînement, 12 732 lignes de test, 601 événements proxy en
train, 156 en test.

| Métrique | Résultat |
|---|---:|
| Average precision | **14,07 %** |
| Prévalence de référence | 1,23 % |
| Lift vs prévalence | **11,48×** |
| ROC-AUC | **0,878** |
| Precision au seuil machine | 12,29 % |
| Recall au seuil machine | 23,72 % |
| Taux d'alerte | **2,36 %** (301 / 12 732 cycles) |

**Lecture correcte** : le score classe mieux les trajectoires associées à une
séquence future instable que le hasard (~11,5× la prévalence en average
precision) ; au seuil choisi, ~2,4 % des cycles sont signalés et 23,7 % des
séquences labellisées sont retrouvées. **Ce n'est pas** une probabilité calibrée,
une cause de rebut, une garantie de précision sur une usine réelle, ni un
modèle prêt à commander une machine.

## 7. Limites assumées

- Données et cible **synthétiques** ; le proxy `scrap_flag` futur ne remplace pas
  une mesure qualité ou une alarme SPC validée.
- Score **non causal et non calibré** ; le percentile 98 n'est pas universel.
- Généralisation non démontrée à une autre matière, recette, moule, cavité,
  machine ou capteur.
- Manquent : tolérances versionnées, mesures de masse/cotes/warpage/aspect,
  débits de refroidissement, événements maintenance qualifiés.
- Restent à mesurer : délai d'anticipation, fausses alertes par OF, changements
  de recette, abstention hors domaine.
- **Aucune action automatique** ; statut présenté : **« prêt pour pilote »**,
  jamais « validé sur le terrain ».

## 8. Conclusion

La veille confirme qu'aucune solution du marché ne fournit un seuil universel de
dérive pour la plasturgie : le contexte machine-matière-moule domine. Le choix
IDDRV est donc un **empilement explicable et local** : règles de tolérance
(autoritaires), HDT (priorité d'inspection par anomalie multivariée), puis
investigateur déterministe (preuves) et décision humaine. Le ML ne remplace pas
les fiches de réglage ; il **anticipe une inspection** là où les valeurs
individuelles sont encore acceptables.

> « Je ne remplace pas les tolérances par du ML. Les règles restent autoritaires
> pour les dépassements connus. HDT apprend le comportement normal de chaque
> machine et détecte une volatilité multivariée inhabituelle avant une séquence
> instable. Il donne une priorité d'inspection. Le moteur déterministe fournit
> ensuite les preuves et l'humain décide. Les scores viennent d'un holdout
> synthétique : le modèle n'est pas validé terrain. »

## 9. Preuves

- `source-plasturgie/veille-index/journal-veille.md` — journal daté S01–S13 (C6)
- `source-plasturgie/veille-index/feature-to-defect-matrix.md` — hypothèses prudentes (C6)
- `source-plasturgie/veille-index/README.md` — méthodologie C6/C7/C8
- `source-plasturgie/euromap/` — EUROMAP 77/83/101/102 (interopérabilité)
- `ml/HDT-process-drift.md` — définition, contrat, protocole (C7/C8)
- `ml/VALIDATION-HDT.md` — exécution de référence et métriques (C8)
- `ml/process_drift.py` — features, split, entraînement, prédiction (C8)
- `models/process_drift_hdt_v1.meta.json` — contrat, split, métriques versionnés (C8)
- `models/rebut_risk_v1.meta.json` — baseline logistique conservée (C7)
- `note/2026-08-03.md` — décisions de cadrage (C7)
