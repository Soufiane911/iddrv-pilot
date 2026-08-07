# Validation HDT — résultat de référence

Date de l'exécution : 2026-08-03.

## Commandes

```bash
python scripts/train_process_drift.py
python -m pytest -q tests/test_process_drift.py tests/test_rebut_risk.py
```

## Jeu et protocole

| Élément | Valeur |
|---|---:|
| Lignes d'entraînement | 25 461 |
| Lignes de test | 12 732 |
| Événements d'instabilité train | 601 |
| Événements d'instabilité test | 156 |
| Horizon | 20 cycles |
| Label | au moins 3 rebuts dans les 20 cycles futurs |
| Split | temporel 2/3–1/3 par machine |
| Modèle | Isolation Forest par machine |
| Population normale | cycles historiques `scrap_flag = 0` |

Les nombres de rebuts futurs servent ici de proxy de séquence instable. Ce
n'est pas une mesure de performance terrain.

## Résultats holdout

| Métrique | Résultat |
|---|---:|
| Average precision | **14,07 %** |
| Prévalence de référence | **1,23 %** |
| Lift vs prévalence | **11,48×** |
| ROC-AUC | **0,878** |
| Precision au seuil machine | **12,29 %** |
| Recall au seuil machine | **23,72 %** |
| Taux d'alerte | **2,36 %** |
| Alertes | **301 / 12 732** |

## Lecture correcte

Le score classe mieux les trajectoires associées à une séquence future instable
que le classement aléatoire, avec environ 11,5 fois la prévalence en average
precision. Au seuil choisi, environ 2,4 % des cycles sont signalés et 23,7 %
des séquences labellisées sont retrouvées.

Cela ne signifie pas :

- qu'une alerte est une probabilité de 14 % ;
- qu'une alerte est une cause de rebut ;
- que 12,3 % de précision seront obtenus sur une usine réelle ;
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
