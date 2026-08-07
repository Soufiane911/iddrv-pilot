# Index de veille plasturgie — rapport E2

## Objet et périmètre

Ce dossier est le registre de travail pour la veille injection plastique d'IDDRV. Il ne
remplace ni une qualification process, ni une fiche matière, ni une preuve de
causalité. Les relations de la [matrice paramètres-défects](./feature-to-defect-matrix.md)
sont des hypothèses à confronter aux cycles, aux lots matière, au moule, aux mesures
dimensionnelles et aux événements de maintenance.

Le journal utilise les statuts suivants :

- **lu — page** : la page indiquée a été ouverte et son contenu utile vérifié ;
- **lu — résumé** : le résumé et les métadonnées publiques ont été vérifiés, mais
  pas le texte intégral ;
- **lu — contenu ciblé** : les passages utiles d'une page ou d'un article ont été
  vérifiés, sans prétendre à une lecture exhaustive ;
- **à lire** : piste repérée, qui ne doit pas être présentée comme une source
  consultée ni servir seule à une décision.

La date d'accès et le niveau de lecture sont dans
[`journal-veille.md`](./journal-veille.md). Une source « lu » n'est donc pas
nécessairement une validation expérimentale.

## Exploitation pour C6, C7 et C8

### C6 — organiser une veille traçable

1. Partir d'une question opérationnelle : dérive de température, hausse de rebut,
   défaut d'aspect, stabilité du moule ou choix du modèle.
2. Chercher d'abord une source officielle ou un article ouvert ; noter l'URL, la
   date d'accès, le statut de lecture et seulement une synthèse paraphrasée.
3. Séparer dans le journal le fait documenté, l'interprétation pour IDDRV et la
   décision. Une hypothèse de défaut ne devient pas une vérité parce qu'elle est
   plausible.
4. Rejouer la vérification des liens avant le rapport E2 et compléter les entrées
   « à lire » plutôt que de les transformer silencieusement en « lu ».

EUROMAP 77/83 sert ici de repère d'interopérabilité et de vocabulaire machine/MES,
pas de preuve qu'un signal particulier cause un défaut. Les normes, recommandations
constructeur et fiches matière applicables au couple machine-moule-matière restent à
obtenir auprès du site.

### C7 — comparer les approches existantes

Le besoin est découpé en deux fonctions :

| Fonction | Approches comparées | Décision de pilote |
|---|---|---|
| Expliquer un incident et proposer des pistes | règles déterministes locales, puis éventuellement recherche documentaire | conserver le moteur déterministe : il expose des preuves et peut s'abstenir |
| Estimer le risque du prochain rebut | régression logistique, forêts/gradient boosting, réseau neuronal spécialisé | conserver la baseline tabulaire locale `rebut-risk-logistic-v1`, puis benchmarker sur les mêmes découpages temporels |

Les critères de benchmark sont : qualité sur les rebuts rares (average precision,
ROC-AUC, précision/rappel au seuil), calibration, fuite temporelle, explicabilité
atelier, fonctionnement on-premise, coût/latence, robustesse aux valeurs manquantes
et maintenance. Une précision globale seule est insuffisante lorsque le rebut est
minoritaire.

Le LLM cloud n'est pas la solution de prédiction retenue : il n'est ni nécessaire
pour des colonnes numériques de cycle, ni acceptable sans validation de
confidentialité, coût et hallucination. Un RAG ne sera envisagé que lorsqu'un corpus
de manuels et procédures réellement autorisé sera disponible.

### C8 — paramétrer et prouver le modèle

Le contrat actuel, à présenter comme une baseline et non comme une causalité, est :

- cible : `scrap_flag` ; une prédiction est un **score de risque**, pas une
  classification de la cause ;
- variables machine : `cycle_time_s`, `dosing_time_s`, `injection_time_s`,
  `cooling_time_s`, `cushion_mm`, `switchover_position_mm`,
  `switchover_pressure_bar`, `peak_pressure_bar`, `clamp_force_kn`,
  `mold_temperature_c`, températures fourreau zones 1 à 3, `oil_temperature_c`,
  `energy_kwh`, ainsi que `machine_erp_ref` ;
- historique causal décalé : `previous_scrap_flag` et
  `rolling_scrap_rate_20` (jamais le label du cycle courant) ;
- prétraitement : imputation médiane + standardisation des numériques, imputation
  du mode + one-hot des catégories ;
- `LogisticRegression(solver="lbfgs", class_weight="balanced", max_iter=1000,
  random_state=42)` ; séparation chronologique 2/3 entraînement, 1/3 test ;
- artefact et métriques : `models/rebut_risk_v1.*` dans le reste du projet. Le
  seuil 0,5 est le seuil courant à challenger selon le coût d'une alerte manquée
  et d'une fausse alerte.

Avant toute mise en production, documenter le lot de données, la fenêtre temporelle,
la prévalence, les métriques par machine/moule/produit, la calibration et une règle
d'abstention. Aucun réglage automatique de température, pression ou force ne doit
être déduit du score.

## Utiliser la matrice pour la dérive et le rebut

1. Construire une baseline par contexte comparable (machine + produit + moule +
   matière), avec unité et qualité de mesure explicites.
2. Comparer niveau, dispersion et tendance des paramètres ; ne pas comparer des
   consignes d'une machine à des valeurs réellement mesurées sans le signaler.
3. Joindre au score les cycles voisins, le taux de rebut, le type de défaut,
   l'OF, le moule, la matière et les événements de maintenance.
4. Utiliser la matrice pour ordonner les vérifications, jamais pour étiqueter
   automatiquement `short shot`, `flash`, `warpage`, bulles ou usure.
5. Confirmer par contrôle pièce, mesure dimensionnelle, inspection du plan de joint,
   contrôle matière et/ou essai encadré. Toute intervention doit être validée par
   le responsable process.

La dérive process (variation progressive d'un signal) et le risque de rebut (cible
ML) sont deux objets différents. Un signal qui dérive peut être une conséquence,
un proxy ou un artefact de capteur. La matrice donne donc un niveau de confiance
documentaire, pas une probabilité issue des données IDDRV.

## Droits, licences et limites de copie

Ne pas copier dans le dépôt le texte intégral, les tableaux, figures, PDF ou extraits
substantiels protégés. Conserver la référence bibliographique, l'URL, la date
d'accès et la licence lorsque la source en fournit une ; respecter les conditions
de réutilisation et citer les auteurs. Les notes de ce dossier sont des synthèses
originales et courtes.

Le journal n'utilise pas et ne doit pas utiliser le fichier d'évaluation
`data/scenarios/industrial_demo/ground_truth.json`. Les données de scénario servent
à tester le logiciel, pas à justifier une loi physique issue de la veille.

## Limites et suite

La veille vérifiée ci-dessous couvre surtout l'interopérabilité, les méthodes ML et
les relations générales température/pression/refroidissement/warpage. Elle ne valide
pas une fenêtre process pour une résine ou un moule donné, ne remplace pas les
fiches constructeur, et ne contient pas encore de source primaire locale sur le
séchage matière, les bulles, la force de fermeture admissible ou l'usure du moule
IDDRV. Ces points restent « à lire » ou à confirmer expérimentalement.
