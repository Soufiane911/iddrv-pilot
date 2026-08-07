# Articles open access — injection plastique et qualité prédictive

Sélection réalisée le 3 août 2026 à partir de recherches Crossref et OpenAlex, puis vérifiée dans les PDF. Les cinq articles ci-dessous sont publiés en accès ouvert et portent une mention explicite **Creative Commons Attribution (CC BY) 4.0** dans le PDF (la licence est également remontée par Crossref). Les liens DOI renvoient vers la notice de l’éditeur ; les fichiers locaux sont des PDF valides téléchargés depuis les plateformes éditeur.

## Synthèse rapide

| Article | Cible | Approche | Signal ou paramètres particulièrement exploitables |
|---|---|---|---|
| Zhou et al. (2023) | Short-shot | BPNN et transfer learning | Profils de pression/vitesse d’injection, position de fin d’injection, temps de remplissage, températures matière, maintien |
| Ardestani et al. (2023) | Blush (défaut visuel au voisinage du seuil) | DOE, ANOVA, ANN, GA/PSO | Débit, température matière, pression de maintien, diamètre du canal, géométrie du seuil |
| Ke & Huang (2020) | Qualité dimensionnelle (trois largeurs) | Indices de pression + MLP | Pression de maintien, intégrale de pression, chute de pression résiduelle, pression de pic |
| Párizs et al. (2022) | Masse : sous-compensation / acceptable / sur-compensation | kNN, Naïve Bayes, arbre, LDA | 19 caractéristiques extraites de courbes de pression cavité/canal |
| Wang et al. (2017) | Warpage | Kriging/processus gaussien + EGO | Pression cavité, températures, remplissage/maintien, paramètres vibratoires |

## Fiches détaillées

### 1. Prediction of Short-Shot Defects in Injection Molding by Transfer Learning

- **Auteurs :** Zhe-Wei Zhou, Hui-Ya Yang, Bei-Xiu Xu, Yu-Hung Ting, Shia-Chung Chen, Wen-Ren Jong.
- **Année :** 2023.
- **DOI / URL :** [10.3390/app132312868](https://doi.org/10.3390/app132312868) ; [version éditeur](https://www.mdpi.com/2076-3417/13/23/12868).
- **Licence :** CC BY 4.0, indiquée sur la première page du PDF : [creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/).
- **Résumé :** un réseau de neurones BPNN prédit avant ouverture du moule si une pièce présente un remplissage incomplet. Deux transferts sont étudiés : simulation CAE vers données réelles pour le moule LT60, puis LT60 réel vers LT100 réel. Le système est intégré à la machine pour fournir une alerte pendant le cycle.
- **Paramètres/features exploitables :** données de simulation Moldex3D et données de remplissage réelles ; position de fin d’injection, commutation vitesse/pression (VP), temps de remplissage, maxima/minima de pression et de vitesse d’injection, températures matière moyennes, temps/pressions de maintien, temps de refroidissement et positions d’injection. Les profils de pression et de vitesse sont résumés de 71 points à 66 entrées ; une sélection par corrélation de Pearson (seuil retenu : 0,04) est appliquée.
- **Défaut étudié :** short-shot / remplissage incomplet, étiquette binaire (short-shot ou non). Les pièces sont des plaques longues LT60/LT100 en ABS.
- **Méthode ML/statistique :** BPNN (MLP feed-forward) avec apprentissage par rétropropagation ; pré-entraînement CAE puis transfer learning sur données machine. Le modèle de base sans transfert sert de comparaison.
- **Métriques et résultats rapportés :** exactitude de validation de 90,2 % pour LT60 avec transfert (88,5 % sans transfert) et 94,4 % pour LT100 avec transfert (91,0 % sans transfert). Le tableau de comparaison utilise respectivement 1 100/122 et 576/144 observations entraînement/validation. Le déploiement annonce une prédiction pendant le cycle de 16 s, au lieu d’attendre le démoulage/refroidissement.
- **Limites :** l’étude est centrée sur deux géométries de plaques, un matériau et une machine ; le modèle exploite des simulations CAE et des essais spécifiques. Les performances publiées sont des exactitudes de validation, sans rappel, précision, F1 ou matrice de confusion ; une validation externe sur d’autres moules, matières et régimes de procédé reste nécessaire.
- **Fichier local :** `prediction-short-shot-defects-transfer-learning-2023.pdf`.

### 2. Application of Machine Learning for Prediction and Process Optimization—Case Study of Blush Defect in Plastic Injection Molding

- **Auteurs :** Alireza Mollaei Ardestani, Ghasem Azamirad, Yasin Shokrollahi, Matteo Calaon, Jesper Henri Hattel, Murat Kulahci, Roya Soltani, Guido Tosello.
- **Année :** 2023.
- **DOI / URL :** [10.3390/app13042617](https://doi.org/10.3390/app13042617) ; [version éditeur](https://www.mdpi.com/2076-3417/13/4/2617).
- **Licence :** CC BY 4.0, indiquée sur la première page du PDF : [creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/).
- **Résumé :** l’article quantifie et réduit le blush, halo blanchâtre généralement situé près du seuil, sur une bague en PVC. Une phase de screening puis un plan composite central relient les paramètres d’injection à l’aire du défaut ; des réseaux neuronaux prédisent ensuite cette aire et un algorithme génétique recherche un réglage réduit.
- **Paramètres/features exploitables :** huit variables : débit, température matière, température moule, pression de maintien, diamètre du canal, diamètre du seuil, angle du seuil et angle inclus. Les quatre facteurs les plus significatifs par ANOVA sont le diamètre du canal, la pression de maintien, le débit et la température matière. La cible est l’aire du blush mesurée comme une ellipse sur simulation et images expérimentales.
- **Défaut étudié :** blush, défaut d’aspect autour du seuil (et non flash/warpage). La mesure expérimentale est l’aire de la zone visible ; le modèle FEA associe le blush à une zone dépassant la contrainte de cisaillement admissible du PVC.
- **Méthode ML/statistique :** DOE factoriel fractionnaire (32 essais), ANOVA et régression ; plan composite central à cinq niveaux ; ANN de base, ANN + PSO et ANN + GA ; GA final pour optimiser les quatre paramètres influents. Les données ANN sont séparées 70 % entraînement, 15 % validation, 15 % test.
- **Métriques et résultats rapportés :** l’écart absolu moyen entre FEA et quatre essais expérimentaux de validation est de 5,6 %. L’article rapporte 99,99 % d’« accuracy » d’entraînement pour le meilleur ANN de base contre 86,57 % pour l’ANOVA, ainsi qu’une erreur moyenne de prédiction de 1,3 % dans le résumé. Le réglage trouvé par GA réduit l’aire du blush de 81,7 % par rapport au réglage initial ; la validation FEA/expérience doit être distinguée de la performance de généralisation ML.
- **Limites :** une seule pièce, une matière PVC, un moule et une plage de paramètres sont étudiés. L’aire est approximée par une ellipse et la majorité des données vient de FEA ; seuls quatre essais servent à la validation FEA. Les résultats ne constituent donc pas une garantie pour une autre matière, cavité ou machine. L’« accuracy » annoncée est surtout une mesure d’ajustement/prédiction relative aux réponses FEA, pas une métrique industrielle de classification de rebuts.
- **Fichier local :** `blush-defect-ml-process-optimization-2023.pdf`.

### 3. Quality Prediction for Injection Molding by Using a Multilayer Perceptron Neural Network

- **Auteurs :** Kun-Cheng Ke, Ming-Shyan Huang.
- **Année :** 2020.
- **DOI / URL :** [10.3390/polym12081812](https://doi.org/10.3390/polym12081812) ; [version éditeur](https://www.mdpi.com/2073-4360/12/8/1812).
- **Licence :** CC BY 4.0, indiquée sur la première page du PDF : [creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/).
- **Résumé :** au lieu de juger la qualité avec les seuls réglages machine, l’étude utilise les courbes de pression dans le moule, qui reflètent directement l’écoulement et le compactage. Des indices corrélés à la géométrie alimentent un MLP pour prédire trois largeurs de la pièce.
- **Paramètres/features exploitables :** onze indices sont extraits des profils de pression ; les indices retenus sont la pression de maintien de première phase (`Phindex`), l’intégrale de pression (`PIindex`), la chute de pression résiduelle (`Prindex`) et la pression de pic (`Ppindex`), selon plusieurs positions de capteurs. Les réglages physiques à interpréter sont notamment température matière/moule, vitesse et pression d’injection, commutation V/P, pression et temps de maintien.
- **Défaut étudié :** défauts dimensionnels / stabilité géométrique, avec trois largeurs mesurées (`W1`, `W2`, `W3`) comme cibles continues. L’article discute aussi retrait et warpage, mais ne les utilise pas comme cibles principales de ce modèle.
- **Méthode ML/statistique :** corrélations de Pearson pour filtrer les indices (seuil de corrélation supérieur à 0,75), puis MLP à une couche cachée ; comparaison de groupes d’indices et du ratio neurones cachés/entrées. Les essais proviennent d’un cas de moulage instrumenté.
- **Métriques et résultats rapportés :** 356 points d’entraînement et 89 points de test. Les groupes d’indices retenus dépassent 90 % d’exactitude de prédiction ; la largeur `W3` atteint 93 %. Les corrélations de `Phindex` avec `W1/W2/W3` sont 0,96/0,96/0,97 et celles de `Ppindex` 0,94/0,95/0,94.
- **Limites :** petit jeu de données et étude de cas unique ; la publication rapporte principalement une exactitude, sans intervalle d’incertitude ni MAE/RMSE détaillé par largeur. Les corrélations ne prouvent pas une causalité et la transposition à une autre géométrie, matière, capteur ou fenêtre de procédé doit être vérifiée.
- **Fichier local :** `quality-prediction-mlp-2020.pdf`.

### 4. Machine Learning in Injection Molding: An Industry 4.0 Method of Quality Prediction

- **Auteurs :** Richárd Dominik Párizs, Dániel Török, Tatyana Ageyeva, József Gábor Kovács.
- **Année :** 2022.
- **DOI / URL :** [10.3390/s22072704](https://doi.org/10.3390/s22072704) ; [version éditeur](https://www.mdpi.com/1424-8220/22/7/2704).
- **Licence :** CC BY 4.0, indiquée sur la première page du PDF : [creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/).
- **Résumé :** des classifieurs simples prédisent en ligne une classe de qualité d’une pièce multi-cavités à partir de signaux de pression. Le protocole utilise un moule 16 cavités, huit capteurs de pression et 190 pièces ABS ; la masse est employée comme indicateur pratique de stabilité/qualité.
- **Paramètres/features exploitables :** 19 caractéristiques dérivées de courbes échantillonnées à 100 Hz pendant 10 s : intégrales de pression, pression maximale, instant du maximum, temps de début, gradients autour du maximum et différence d’intégrales entre capteurs. Les données de procédé comprennent notamment pression de maintien (200/600/1000 bar), temps de maintien (0 à 3 s), température matière 225 °C et moule 40 °C.
- **Défaut étudié :** non-conformité dimensionnelle/poids indirecte : classes `Undercompensated`, `Acceptable` (masse 0,470–0,475 g) et `Overcompensated`. Ce n’est pas une détection visuelle de flash ou de short-shot, mais une bonne base de monitoring de compensation et de scrap lié au poids.
- **Méthode ML/statistique :** k plus proches voisins, Naïve Bayes, arbre de décision binaire et analyse discriminante linéaire ; comparaison du jeu complet (19 variables), de huit composantes principales et d’une sélection forward. Cent tirages aléatoires sont évalués pour chaque nombre de points d’apprentissage par classe.
- **Métriques et résultats rapportés :** exactitude moyenne pour 10 points d’apprentissage par classe : kNN 85,14 %, Naïve Bayes 88,27 %, arbre 93,61 %, LDA 86,26 %. Avec seulement deux points par classe, l’arbre atteint en moyenne 90,97 % (75,54–97,28 % selon le tirage). Le temps de classification de l’arbre est de 8–10 s ; l’étude recommande l’arbre comme meilleur compromis.
- **Limites :** 190 pièces, une matière ABS, un moule et une machine ; la classe acceptable est volontairement très étroite et la masse ne couvre pas tous les défauts visuels ou dimensionnels. Les répétitions sont des tirages aléatoires issus du même lot de données, pas une séparation temporelle ou inter-moule ; les performances peuvent donc surestimer la robustesse en production.
- **Fichier local :** `ml-quality-prediction-industry-4-0-2022.pdf`.

### 5. Pressure Analysis of Dynamic Injection Molding and Process Parameter Optimization for Reducing Warpage of Injection Molded Products

- **Auteurs :** Xinyu Wang, Hongxia Li, Junfeng Gu, Zheng Li, Shilun Ruan, Changyu Shen, Minjie Wang.
- **Année :** 2017.
- **DOI / URL :** [10.3390/polym9030085](https://doi.org/10.3390/polym9030085) ; [version éditeur](https://www.mdpi.com/2073-4360/9/3/85).
- **Licence :** CC BY 4.0, indiquée dans le PDF : [creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/).
- **Résumé :** l’article propose une simulation par éléments finis de l’injection dynamique (DIMT), avec force vibratoire, et l’optimise par modèle de processus gaussien. Trois structures et matériaux sont comparés pour analyser la pression en cavité et réduire le warpage.
- **Paramètres/features exploitables :** température matière et moule, temps de remplissage et de maintien, pression initiale, amplitude et fréquence de vibration, paramètres dynamiques de remplissage et de compactage. La pression transitoire en cavité et la pression moyenne au seuil sont utilisées pour interpréter le mécanisme.
- **Défaut étudié :** warpage après éjection, mesuré en millimètres ; l’article examine aussi l’effet indirect des contraintes résiduelles et de l’hétérogénéité de l’historique thermo-mécanique.
- **Méthode ML/statistique :** éléments finis pour la simulation, modèle de substitution de Kriging (processus gaussien) et optimisation séquentielle EGO fondée sur l’amélioration attendue. Ce n’est pas un classifieur de défauts, mais une optimisation prédictive des paramètres process.
- **Métriques et résultats rapportés :** les tableaux comparent le warpage initial et optimisé pour trois cas, en régime conventionnel et dynamique ; par exemple, pour le capot PC/ABS, le cas dynamique passe de 0,131 à 0,094 mm et le cas conventionnel de 0,405 à 0,221 mm. Les valeurs sont des sorties de simulation optimisées, pas une métrique de classification.
- **Limites :** l’étude est principalement numérique et la DIMT n’est pas avantageuse pour les structures grandes et étroites ; l’effet vibratoire reste concentré près du seuil. Une validation expérimentale et une généralisation à d’autres moules, matières et équipements sont nécessaires.
- **Fichier local :** `warpage-pressure-process-optimization-2017.pdf`.

## Remarques d’usage

- Ces articles fournissent des variables directement réutilisables pour un schéma de données : identifiant de cycle, profils pression/vitesse/température, paramètres de maintien/refroidissement, masse et mesures dimensionnelles, puis étiquette de défaut.
- Les métriques ne sont pas directement comparables : classification binaire/multiclasse, régression d’aire, et prédiction dimensionnelle utilisent des jeux de données et des protocoles différents. Pour un futur modèle scrap/non-scrap, conserver un jeu de test temporel et rapporter au minimum précision, rappel, F1, matrice de confusion et taux de faux rebuts.
- Aucun PDF d’article sans licence explicite n’a été copié dans ce lot.
