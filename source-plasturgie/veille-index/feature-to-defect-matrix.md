# Matrice prudente paramètres → défauts

Cette matrice est un **guide d'hypothèses d'investigation**, pas un modèle causal et
pas une table de décision automatique. Une flèche « plus élevé » ou « plus faible »
signifie « écart au régime stable comparable », non une valeur universelle. Les effets
dépendent au minimum de la matière, de la géométrie, du point d'injection, du moule,
des capteurs et du réglage de la machine.

## Niveaux

- **Élevé** : mécanisme général documenté, mais confirmation locale indispensable ;
- **Moyen** : relation plausible et documentée indirectement ou très dépendante du contexte ;
- **Faible** : signal de triage ou proxy à vérifier, pas une cause à annoncer.

Les références **S01–S13** sont détaillées dans [`journal-veille.md`](./journal-veille.md).
S06 et S11 ont été ouvertes et vérifiées sur les passages utiles ; S07–S10 seulement par résumé public.

## Matrice

| Paramètre observé / dérive | Écart ou condition à examiner | Défaut possible | Confiance | Pourquoi cette association, sans surinterpréter | Source(s) | Vérification atelier attendue |
|---|---|---|---|---|---|---|
| `barrel_temp_zone2_c` (température zone 2) | baisse, oscillation ou écart à la recette stable | short shot / remplissage incomplet | Moyenne | Une température de fusion ou un régime thermique inadéquat peut réduire la fluidité ; la zone 2 seule ne suffit pas à établir la température de fusion ni la cause. | S06, S07, S11 | comparer zones 1–3, température réelle et pression/position de commutation ; contrôler remplissage et matière |
| `barrel_temp_zone2_c` | hausse persistante, points chauds ou instabilité | bulles, brûlures ou dégradation | Faible | Hypothèse dépendante de la résine, de l'humidité et de la ventilation ; la veille vérifiée ici ne permet pas de fixer un seuil ni de confondre bulle, vide et brûlure. | S07, S11 ; S13 à lire | fiche matière, séchage, évents, inspection coupe/section et analyse défaut |
| `peak_pressure_bar` / pression d'injection | trop faible ou montée interrompue, à géométrie et matière constantes | short shot | Moyenne | La pression et la vitesse d'injection font partie des paramètres de remplissage cités par les revues ; un signal faible peut aussi venir d'un capteur ou d'une commutation mal réglée. | S06, S07, S09 | vérifier pression/position de commutation, coussin, masse pièce et empreintes |
| `peak_pressure_bar` / pression d'injection | niveau élevé **avec** plan de joint qui s'ouvre ou maintien insuffisant | flash / bavure | Faible à moyenne | La pression pousse la matière ; cette association physique est plausible, mais les sources vérifiées ici ne donnent pas de seuil flash. Le flash nécessite aussi un plan de joint, une fermeture et un état de moule compatibles. | S07, S08 (pression générale) ; S13 à lire | inspecter plan de joint, alignement, évents et force réellement disponible |
| `peak_pressure_bar` + pression de maintien | maintien élevé ou trop long, selon matière/géométrie | retrait différentiel, contraintes, parfois warpage | Faible à moyenne | Les revues relient pression de maintien, refroidissement et retrait/warpage, mais le sens de l'effet varie selon la pièce. | S06, S11 | mesure dimensionnelle multi-axes, poids pièce, DOE local |
| `switchover_position_mm` / `switchover_pressure_bar` | commutation qui dérive par rapport aux cycles bons | short shot, variation de poids ou défaut dimensionnel | Faible à moyenne | C'est un indicateur de stabilité du remplissage/maintien ; il ne discrimine pas à lui seul un défaut de matière, de moule ou de capteur. | S07, S08 | aligner tendance de commutation, coussin, pression, masse et défaut par empreinte |
| `cooling_time_s` | trop court ou variation entre cycles | warpage, retrait ou pièce insuffisamment stabilisée | Moyenne à élevée | S06 décrit explicitement la durée de refroidissement parmi les paramètres influençant warpage et retrait ; le réglage optimal reste pièce- et matière-dépendant. | S06, S11 | température pièce à démoulage, mesure après stabilisation, température et débit des circuits |
| `cooling_time_s` | hausse progressive sans changement de recette | cycle time en hausse, possible dérive thermique | Moyenne | Le refroidissement est une part importante du cycle ; la hausse est un signal de dérive, pas un défaut produit en soi. | S11 | décomposer `cycle_time_s`, contrôler débit, échange thermique, encrassement et température moule |
| `mold_temperature_c` | non-uniformité ou variation cyclique | warpage / retrait différentiel | Moyenne à élevée | La température du moule figure parmi les paramètres examinés pour warpage/retrait ; l'homogénéité et le gradient sont souvent plus informatifs que la moyenne. | S06, S11 | capteurs aller/retour et zones, thermographie si autorisée, mesure dimensionnelle |
| `clamp_force_kn` / force de fermeture | insuffisante pour la pression et la surface projetée | flash / bavure | Moyenne | Un effort de fermeture insuffisant est compatible avec une ouverture du plan de joint, mais il faut vérifier surface projetée, pression, usure et réglage ; ce n'est pas un seuil universel. | S06 (force de fermeture et qualité), S07, S08 ; S13 à lire | calcul/fiche machine, effort réel, plan de joint et état des colonnes/moule |
| `clamp_force_kn` | excessive ou mal répartie | contraintes, difficulté de démoulage ou usure accélérée | Faible | Signal de risque de réglage et de mécanique ; aucune source vérifiée ici ne permet de déduire un défaut précis avec ce seul champ. | S08 ; S13 à lire | manuel machine, parallélisme, empreintes, éjection et inspection outillage |
| `cycle_time_s` | raccourcissement concomitant d'un refroidissement insuffisant | warpage / retrait ou défaut de stabilité | Moyenne | Le temps de cycle est un agrégat : il faut retrouver sa décomposition, car une baisse peut venir de l'injection, du refroidissement ou de l'ouverture. | S06, S11 | analyser `injection_time_s`, `cooling_time_s`, ouverture moule et dimension après stabilisation |
| `cycle_time_s` | hausse lente, par moule ou OF | signal de dérive, pas défaut déterminé | Faible | Peut refléter refroidissement, dosage, maintenance ou changement de recette ; utile pour alerte de tendance seulement. | S08, S11 | segmenter machine/OF/moule/matière et vérifier événements maintenance |
| matière, taux de fibres, nombre de cycles et inspections moule | charge abrasive ou usure progressive | usure moule, dérive dimensionnelle, aspect | Élevée pour l'usure abrasive des GFRP ; faible pour le défaut IDDRV | Le résumé S10 rapporte l'usure abrasive de cavités/canaux avec les plastiques renforcés fibres de verre. Le passage à une cote hors tolérance demande une métrologie du moule et de la pièce. | S10 ; spécification S12 à lire | matière/charge, compteur de cycles, mesure de cavité/plan de joint, maintenance et dimensions |
| débit/équilibre de refroidissement (non présent dans le contrat ML actuel) | circuit partiellement obstrué ou gradient entre empreintes | warpage / retrait différentiel | Moyenne à élevée | Les revues relient conception/efficacité du refroidissement et warpage ; le débit réel est une donnée manquante à ajouter seulement si instrumentée. | S06, S11 | mesurer débit/aller-retour par circuit et comparer les empreintes |
| humidité/séchage matière (non présent dans le contrat ML actuel) | matière humide ou séchage hors spécification | bulles, vides, aspect ou propriétés dégradées | Faible dans cette veille | Association d'atelier plausible, mais aucune fiche matière/étude spécifique au grade IDDRV n'a été vérifiée ; ne pas l'utiliser comme règle. | S13 à lire | fiche matière, traçabilité séchage, point de rosée et contrôle de section |

## Règles d'utilisation

1. **Une ligne ne déclenche jamais une action seule.** Il faut au moins une tendance
dans un contexte comparable, un défaut observé et une preuve de qualité.
2. **Ne pas confondre corrélation et cause.** Température, pression et cycle sont
couplés ; un réglage peut être la réponse à un problème initial.
3. **Conserver les absences.** Débit de refroidissement, humidité, pression cavité,
empreinte et mesure dimensionnelle ne sont pas inventés à partir d'une colonne
voisine ; une donnée manquante reste manquante.
4. **Pour le modèle de rebut**, les lignes servent à choisir des contrôles et des
features candidates. Elles ne doivent pas servir à fabriquer le label `scrap_flag`
ni à injecter le défaut attendu dans le cycle courant.
5. **Pour la dérive**, calculer baseline, pente, dispersion et taux de valeurs
manquantes par machine + produit + moule + matière, puis faire relire l'alerte par
un responsable process.

## Limites

La matrice ne contient pas de seuil numérique, car aucun couple résine–géométrie–moule
du site n'a été documenté dans les sources vérifiées. Les niveaux sont des niveaux de
confiance documentaire, pas des performances mesurées sur IDDRV. Les relations
« bulles », « flash » et usure nécessitent en particulier les documents S10/S13,
une inspection physique et une validation expérimentale avant tout usage opérateur.
