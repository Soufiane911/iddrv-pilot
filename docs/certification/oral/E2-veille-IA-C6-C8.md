# Épreuve E2 — Veille et choix d'une solution d'IA

**Compétences :** C6 à C8 — **Durée :** 15 minutes

## Message central

Le projet ne remplace pas les fiches de réglage par une boîte noire. Une valeur
hors tolérance reste traitée par une règle déterministe. Le modèle HDT (*Horizon
de dérive sous tolérance*) complète ce contrôle en détectant une volatilité
multivariée inhabituelle avant une séquence instable.

```text
Règles de tolérance → HDT IsolationForest → DeterministicInvestigator → décision humaine
```

HDT fournit une priorité d'inspection. Il ne commande pas la presse, ne modifie
pas un réglage et ne constitue pas une preuve causale.

## 1. Besoin

Une machine peut rester dans les tolérances instantanées alors que la
variabilité conjointe du temps de cycle, de la pression, du refroidissement, de
la température du moule ou de l'énergie augmente. Le besoin est donc de repérer
une trajectoire qui devient instable assez tôt pour inspecter la machine.

Contraintes : on-premise, confidentialité, explicabilité, reproductibilité et
absence de dépendance LLM/RAG/OpenAI en production.

## 2. Veille réalisée

Les sources sont conservées dans `source-plasturgie/` :

- EUROMAP 77/83 : vocabulaire et interopérabilité des données machine ;
- articles open access : short-shot, blush, pression, compensation, qualité
dimensionnelle et warpage ;
- ressources HAL : pilotage, capteurs pression/température, qualité et usure ;
- NIST : énergie et tolérances du procédé.

La veille confirme que les effets dépendent de la matière, du moule, de la
cavité, de la géométrie, de la recette et des capteurs. Elle ne fournit donc
aucun seuil universel transférable à IDDRV.

## 3. Benchmark et décision

| Approche | Force | Limite | Décision |
|---|---|---|---|
| Règles de tolérance | Autoritaires, locales, auditables | Peu adaptées aux dérives conjointes | Référence et fallback |
| SPC / EWMA / CUSUM | Détecte tendance et dispersion | Limites à valider par contexte | Prochaine extension |
| Régression logistique rebut | Simple, reproductible | Labels rares, modèle faible sur le holdout | Baseline conservée |
| Isolation Forest HDT | Peu de labels, détecte des trajectoires inhabituelles | Score non calibré, validation terrain nécessaire | Modèle retenu |
| LLM/RAG cloud | Synthèse possible | Confidentialité, coût, hallucination, corpus absent | Reporté |

La régression logistique `rebut-risk-v1` reste une baseline historique. HDT est
retenu car il répond au problème utile : détecter une dérive avant de contrôler
un rebut déjà produit.

## 4. Paramétrage HDT

- `sklearn.ensemble.IsolationForest` ;
- 200 arbres, `random_state=42` ;
- imputation médiane et standardisation ;
- modèle normal contextualisé par `machine_erp_ref` ;
- entraînement sur les cycles historiques `scrap_flag = 0` ;
- seuil au 98e percentile de la population normale ;
- fenêtre de volatilité : 20 cycles ;
- horizon d'anticipation : 20 cycles.

Features principales : volatilité du temps de cycle, temps d'injection,
refroidissement, pression de pointe, force de fermeture, température moule,
température zone 2 et énergie.

La cible offline actuelle vaut 1 lorsqu'au moins trois rebuts apparaissent dans
les 20 cycles futurs. C'est un **proxy synthétique d'instabilité**, pas une
vérité industrielle universelle. En production, il sera remplacé par une
excursion SPC ou qualité validée.

## 5. Résultats du holdout synthétique

Split temporel 2/3–1/3 à l'intérieur de chaque machine :

| Métrique | Résultat |
|---|---:|
| Average precision | 14,07 % |
| Prévalence | 1,23 % |
| Lift | 11,48× |
| ROC-AUC | 0,878 |
| Precision au seuil | 12,29 % |
| Recall | 23,72 % |
| Taux d'alerte | 2,36 % |

Ces métriques montrent un classement utile sur le holdout synthétique, mais ne
valident pas une usine réelle. `anomaly_score` n'est pas une probabilité.

## 6. Réponse orale recommandée

> « Je ne remplace pas les tolérances par du ML. Les règles restent autoritaires
> pour les dépassements connus. HDT apprend le comportement normal de chaque
> machine et détecte une volatilité multivariée inhabituelle avant une séquence
> instable. Il donne une priorité d'inspection. Le moteur déterministe fournit
> ensuite les preuves et l'humain décide. »

## Preuves

- `source-plasturgie/veille-index/journal-veille.md`
- `source-plasturgie/veille-index/feature-to-defect-matrix.md`
- `source-plasturgie/euromap/README.md`
- `ml/process_drift.py`
- `ml/HDT-process-drift.md`
- `ml/VALIDATION-HDT.md`
- `ml/HDT-certification-update.md`

## Questions probables

- **Pourquoi ne pas utiliser uniquement la fiche de réglage ?** Elle détecte le
  hors-tolérance connu ; HDT vise la dérive conjointe avant le dépassement.
- **Pourquoi pas un LLM ?** Le besoin est numérique, local et explicable ; un
  LLM n'apporte pas de meilleure garantie sur les capteurs.
- **Le modèle est-il validé terrain ?** Non. Il s'agit d'un prototype évalué sur
  données synthétiques, prêt à qualifier avec un export industriel.
- **Que signifie 14,07 % ?** C'est l'average precision, pas une probabilité ;
  elle est comparée à une prévalence de 1,23 %.
