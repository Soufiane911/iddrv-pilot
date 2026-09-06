# Validation HDT — résultat de référence

Date de l'exécution : 2026-08-19.

## Commandes

```bash
.venv-report/bin/python scripts/train_process_drift.py \
  --artifact /tmp/process_drift_hdt_v1.joblib \
  --metadata /tmp/process_drift_hdt_v1.meta.json
.venv-report/bin/python -m pytest -q tests/test_process_drift.py tests/test_rebut_risk.py
```

## Jeu et protocole

| Élément | Valeur |
|---|---:|
| Lignes brutes chargées | 38 313 |
| Lignes exploitables après préparation | 38 253 |
| Lignes terminales exclues | 60 (20 par machine) |
| Lignes d'entraînement | 25 500 |
| Lignes de test | 12 753 |
| Événements d'instabilité train | 601 |
| Événements d'instabilité test | 156 |
| Horizon | 20 cycles |
| Label | au moins 3 rebuts dans les 20 cycles futurs |
| Split | temporel 2/3–1/3 par machine |
| Modèle | Isolation Forest par machine |
| Population normale | cycles historiques `scrap_flag = 0` |

Les nombres de rebuts futurs servent ici de proxy de séquence instable. Ce
n'est pas une mesure de performance terrain.

Les bornes `train_end` et `test_start` au niveau global sont des agrégats
inter-machines (respectivement le maximum des fins d'entraînement et le minimum
des débuts de test) ; elles peuvent donc se chevaucher. L'absence de fuite
temporelle se juge sur les bornes `time_boundary.per_machine`, qui sont
strictement ordonnées pour chaque machine.

## Résultats holdout

| Métrique | Résultat |
|---|---:|
| Average precision | **10,98 %** |
| Prévalence de référence | **1,22 %** |
| Lift vs prévalence | **8,97×** |
| ROC-AUC | **0,868** |
| Precision au seuil machine | **9,65 %** |
| Recall au seuil machine | **16,03 %** |
| Taux d'alerte | **2,03 %** |
| Alertes | **259 / 12 753** |

## Lecture correcte

Le score classe mieux les trajectoires associées à une séquence future instable
que le classement aléatoire, avec environ 9 fois la prévalence en average
precision. Au seuil choisi, environ 2 % des cycles sont signalés et 16 %
des séquences labellisées sont retrouvées.

Cela ne signifie pas :

- qu'une alerte est une probabilité calibrée ;
- qu'une alerte est une cause de rebut ;
- qu'une précision mesurée sur ce jeu sera obtenue sur une usine réelle ;
- que le modèle est prêt à commander une machine.

`anomaly_score` est un score de classement non calibré. L'action attendue est
une inspection et une explication, pas un arrêt automatique.

## Comparaison et décision

La version logistique qui tentait de prédire le label futur sur ce jeu synthétique
obtenait un ROC-AUC inférieur au hasard, car la distribution des scénarios et
des machines change fortement entre les périodes. Elle n'est donc pas retenue
comme modèle principal.

L'Isolation Forest contextualisée par machine est retenue comme **prototype HDT**
car elle répond mieux à la question de détection d'anomalie et nécessite moins
de labels. Le modèle de rebut v1 reste conservé comme baseline historique, mais
il ne doit pas être présenté comme la solution métier.

## Risques restant à lever

1. Remplacer le proxy `scrap_flag` futur par un événement de dérive SPC/qualité
   validé par un expert process.
2. Importer les fiches de réglage versionnées pour calculer une marge normalisée
   réelle, sans transformer les tolérances en cible cachée.
3. Tester les changements de recette, de matière, de moule et de capteur.
4. Mesurer le délai d'anticipation et les fausses alertes par OF.
5. Ajouter une validation humaine et un mécanisme d'abstention pour les
   contextes hors domaine.
6. Exposer le score par l'API/UI seulement après validation du contrat runtime.

Statut : **prototype offline évalué, non validé terrain et non intégré comme
commande automatique**.
