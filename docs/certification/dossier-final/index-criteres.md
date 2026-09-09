# Index E1–E5 : exigences et preuves C1–C21

Base observée : `59a4846bb13d31c8fb04b1a2dcfa0239c853605a`. Aucun verdict acquis/non acquis.

Les citations reprennent la colonne « Critère » de **S06**, espaces/retours de ligne normalisés, coquilles conservées. Pages imprimées. S03 est le contrôle complémentaire du référentiel. Les IDs Cx.yy sont créés pour cet index, pas des numéros officiels : C4.08–09 détaillent C4.07 ; C6.07–12 détaillent C6.06. Les appels de notes 1–4 dans S06 renvoient à Valentin Haüy/AcceDe, pas à des exigences supplémentaires. Aucun pourcentage de réussite n’est calculé.

- **Local** : preuve vérifiée localement, strictement microdémo P01 ; couverture globale incomplète.
- **Historique** : résultat consigné par une source identifiée, non rejoué ici.
- **Configuration** : code/document présents, fonctionnement ou exhaustivité non vérifiés.
- **Incomplet** : manque ou action humaine restante. Non audité n’est pas absent.

Chaque section hérite des chemins, commit observé, run/PR, commande, limites et résolution de ses références **P/X/L**, détaillées dans [Inventaire des sources](inventaire-sources.md) et `sources.json`. Une source de branche non fusionnée est un complément séparé, jamais une preuve intégrée à main ou aux livrets. Le fichier `index-preuves.json` fournit une entrée par clause et la prochaine preuve.


## E1 — C1 : Extraction automatisée

Sources : P01, X01, L1, P12. Référentiel complémentaire : S03 p. 1–2.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C1.01 | La présentation du projet et de son contexte est complète : acteurs, objectifs fonctionnels et techniques, environnements et contraintes techniques, budget, organisation du travail et planification. | 2 | **Incomplet**. Faire confirmer acteurs, budget, planning et responsabilités du cas réel ou fictif. |
| C1.02 | Les spécifications techniques précisent : les technologies et outils, les services externes, les exigences de programmation (langages), l’accessibilité (disponibilité, accès). | 2 | **Incomplet**. Spécifier outils, services et règles d’accès pour chaque source autorisée. |
| C1.03 | Le périmètre des spécifications techniques est complet : il couvre l’ensemble des moyens techniques à mettre en œuvre pour l’extraction et l'agrégation des données en un jeu de données brutes final. | 2 | **Incomplet**. Définir un jeu final pertinent et les frontières extraction/agrégation. |
| C1.04 | Le script d’extraction des données est fonctionnel : toutes les données visées sont effectivement récupérées à l’issue de l’exécution du script. | 2 | **Local (P01 seulement)**. Rejouer chaque source visée avec compteurs et empreintes. |
| C1.05 | Le script comprend un point de lancement, l’initialisation des dépendances et des connexions externes, les règles logiques de traitement, la gestion des erreurs et des exceptions, la fin du traitement et la sauvegarde des résultats. | 2 | **Local (P01 seulement)**. Tester lancement, erreurs, connexions et sauvegarde pour les sources externes. |
| C1.06 | Le script d’extraction des données est versionné* et accessible depuis un dépôt Git*. | 2, 3 | **Incomplet**. Vérifier accès au dépôt distant au SHA présenté. |
| C1.07 | L’extraction des données est faite depuis un mix entre au moins les sources suivantes : un service web (API REST), un fichier de données, un scraping, une base de données et un système big data. | 3 | **Incomplet**. Source et moteur big data autorisés, extraction réelle ; HTTP auxiliaire non assimilé à la collecte métier. |

## E1 — C2 : Requêtes SQL

Sources : P01, X01, P12. Référentiel complémentaire : S03 p. 2–3.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C2.01 | Les requêtes de type SQL pour la collecte de données sont fonctionnelles : les données visées sont effectivement extraites suite à l'exécution des requêtes. | 3 | **Local (P01 seulement)**. Exécuter SQL SGBD et big data ; SQLite ne suffit pas. |
| C2.02 | La documentation des requêtes met en lumière choix de sélections, filtrages, conditions, jointures, etc., en fonction des objectifs de collecte. | 3 | **Local (P01 seulement)**. Expliquer sélections/jointures des requêtes réellement livrées. |
| C2.03 | La documentation explicite les optimisations appliquées aux requêtes . | 3 | **Local (P01 seulement)**. Produire EXPLAIN sur volumes représentatifs, sans gain supposé. |

## E1 — C3 : Agrégation et normalisation

Sources : P01, X01. Référentiel complémentaire : S03 p. 3.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C3.01 | Le script d’agrégation des données est fonctionnel : les données sont effectivement agrégées, nettoyées et normalisées en un seul jeu de données à l’issue de l’exécution du script. | 3 | **Local (P01 seulement)**. Rejouer sources autorisées, unités/dates/conflits et jeu final unique. |
| C3.02 | Le script d’agrégation des données est versionné et accessible depuis un dépôt Git. | 3 | **Incomplet**. Vérifier accès distant au script au SHA. |
| C3.03 | La documentation du script d’agrégation est complète : dépendances, commandes, les enchaînements logiques de l’algorithme, les choix de nettoyage et d’homogénéisation des formats données. | 3, 4 | **Local (P01 seulement)**. Étendre la documentation du microdémonstrateur à la chaîne réelle. |

## E1 — C4 : Base de données et RGPD

Sources : P02, P07, L1. Référentiel complémentaire : S03 p. 4–5.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C4.01 | Les modélisations des données respectent la méthode et le formalisme Merise. | 4 | **Incomplet**. Compléter MCD/MLD et correspondance exhaustive aux migrations. |
| C4.02 | Le modèle physique des données est fonctionnel : il est intégré avec succès lors de la création de la base de données, sans erreur. | 4 | **Historique**. Installation à blanc de toutes migrations en bac autorisé. |
| C4.03 | La base de données est choisie au regard de la modélisation des données et des contraintes du projet. | 4 | **Incomplet**. ADR motivant relationnel/temporel, limites et coûts. |
| C4.04 | La reproduction des procédures d’installation décrites (base de données et API) a pour résultat un système conforme aux objets techniques attendus.. | 4 | **Incomplet**. Recette DB/API avec login réel, sans mocks. |
| C4.05 | Le script d’import fourni est fonctionnel : il permet l’insertion des données dans le système mis en place. | 4 | **Historique**. Import applicatif puis relecture persistée. |
| C4.06 | La documentation technique du script d’import est versionné à la racine du même dépôt Git que celui utilisé pour le script d’import. | 4 | **Incomplet**. Vérifier emplacement à la racine du dépôt exigé pour la documentation import. |
| C4.07 | Les documentations techniques des scripts couvrent les parties suivantes : | 4 | **Incomplet**. Contrôler les deux clauses documentaires filles. |
| C4.08 | les dépendances nécessaires pour la réutilisation des scripts (langages, dépendances externes, etc) | 4 | **Incomplet**. Inventorier dépendances et versions de tous scripts import. |
| C4.09 | les commandes pour l’exécution des scripts. | 4, 5 | **Incomplet**. Vérifier commandes sur environnement propre. |
| C4.10 | Le registre des traitements de données personnelles intègre l’ensemble des traitements de données personnelles impliqués dans la base de données. | 5 | **Incomplet**. Faire compléter et approuver tous traitements par responsable compétent. |
| C4.11 | Les procédures de tri des données personnelles pour la mise en conformité de la base de données avec le RGPD sont rédigées. | 5 | **Incomplet**. Rédiger tri sur base, fichiers, exports et sauvegardes. |
| C4.12 | Les procédures de tri détaillent les traitements de conformité (automatisés ou non) à appliquer ainsi que leur fréquence d’exécution. | 5 | **Incomplet**. Faire approuver durées/fréquences puis exercice synthétique. |

## E1 — C5 : API de données

Sources : P03, X01, P09. Référentiel complémentaire : S03 p. 5–6.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C5.01 | La documentation technique de l’API (REST) couvre tous les points de terminaisons. | 5 | **Configuration**. Exporter OpenAPI runtime et comparer toutes routes. |
| C5.02 | La documentation technique couvre les règles d’authentification et/ou d’autorisation de l’API. | 5 | **Configuration**. Vérifier security schemes, rôles, restrictions documentées. |
| C5.03 | La documentation technique respecte les standards du modèle choisi (par exemple OpenAPI*). | 5 | **Configuration**. Valider export et contrat OpenAPI choisi. |
| C5.04 | L’API REST est fonctionnelle pour l’accès aux données du projet : elle restreint par une autorisation (ou authentification) l'accès aux données, | 5 | **Configuration**. Login, révocation/expiration et refus intersites sur DB réelle. |
| C5.05 | L’API REST est fonctionnelle pour la mise à disposition : elle permet la récupération de l’ensemble des données nécessaires au projet, comme prévu selon les spécifications données. | 5 | **Configuration**. Comparer champs/pagination et données importées persistées. |

## E2 — C6 : Veille technique et réglementaire

Sources : P04, L2. Référentiel complémentaire : S03 p. 6–8.

Séances et partage collectif **non audités** ici. Absence constatée d’une preuve de partage dans les pièces sélectionnées ≠ absence de toute pratique.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C6.01 | La thématique de veille choisie porte sur un outil et/ou une réglementation mobilisée dans la mise en situation. | 6 | **Incomplet**. Valider thème utile au projet. |
| C6.02 | Les temps de veille sont planifiés régulièrement (à minima une récurrence d’une heure hebdomadaire). | 6 | **Incomplet**. Planifier au moins une heure hebdomadaire ; conserver séances réellement tenues. |
| C6.03 | Le choix des outils d’agrégation est cohérent avec les sources d’informations visées et le budget disponible (flux RSS, flux réseaux sociaux, agrégation newsletter, etc) | 6 | **Incomplet**. Configurer agrégation cohérente avec sources et budget approuvé. |
| C6.04 | Les synthèses sont communiqués aux parties prenantes dans un format qui respecte les recommandations d’accessibilité (par exemples celles de l’association Valentin Haüy1ou de Atalan - AcceDe2). | 6 | **Incomplet**. Partager réellement une synthèse accessible ; conserver retour expurgé. |
| C6.05 | Les informations partagées dans la synthèse répondent à la thématique de veille choisie. | 6 | **Incomplet**. Relier synthèse recoupée à décision technique. |
| C6.06 | Les sources et flux identifiés répondent aux critères de fiabilité : | 7 | **Incomplet**. Qualifier les six clauses filles pour chaque source. |
| C6.07 | L’auteur de la page est identifié | 7 | **Incomplet**. Identifier auteur institutionnel sans republier données personnelles inutiles. |
| C6.08 | Des informations sur l’auteur sont disponibles et confirment ses compétences, sa notoriété et l’absence d’intérêts personnels | 7 | **Incomplet**. Évaluer compétence, notoriété et conflits d’intérêts, pas neutralité présumée. |
| C6.09 | l’analyse du contenu est valable (date de publication récente, sources de l'information indiquées, niveau de langue correct), | 7 | **Incomplet**. Vérifier date/version, citations et validité du contenu. |
| C6.10 | la source (site) ou le document est structuré | 7 | **Incomplet**. Vérifier structure navigable des sources. |
| C6.11 | les sources (sites) ou documents respectant les normes d'accessibilités sont privilégiés. | 7 | **Incomplet**. Contrôler accessibilité plutôt que la déduire du fournisseur. |
| C6.12 | l’information peut être confirmée par d’autres sites de confiance | 7 | **Incomplet**. Recouper avec sources indépendantes fiables. |

## E2 — C7 : Benchmark des services IA

Sources : P04, P09, X02, L2. Référentiel complémentaire : S03 p. 8–9.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C7.01 | L’expression de besoin est reformulée et présente les objectifs et les contraintes du projet d’intégration d’une solution d’intelligence artificielle. | 7 | **Incomplet**. Faire approuver objectifs et contraintes. |
| C7.02 | Le benchmark liste les services étudiés et les services non étudiés. | 7 | **Incomplet**. Séparer services étudiés, testés, non étudiés. |
| C7.03 | Les raisons pour écarter un service sont explicitées. | 7 | **Incomplet**. Motiver chaque exclusion à partir du besoin. |
| C7.04 | Le benchmark détaille le niveau d’adéquation du service étudié pour chaque ensemble fonctionnel souhaité par le commanditaire. | 8 | **Incomplet**. Comparer par fonctionnalité sur protocole commun. |
| C7.05 | Le benchmark détaille le niveau de la démarche éco-responsable du service étudié, en fonction des informations disponibles. | 8 | **Incomplet**. Sourcer démarche environnementale disponible ; inconnue si non mesurée. |
| C7.06 | Le benchmark détaille les principales contraintes techniques et les pré-requis pour chaque solution. | 8 | **Incomplet**. Documenter contraintes, accès, matériel et dépendances. |
| C7.07 | Les conclusions délimitent clairement les services répondant aux besoins, avec leurs avantages et leurs inconvénients, des services ne couvrant pas les besoins du commanditaire. | 8 | **Incomplet**. Conclure avantages/limites et décision humaine, sans gagnant global. |

## E2 — C8 : Paramétrage du service IA

Sources : P05, P06, L2. Référentiel complémentaire : S03 p. 9–10.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C8.01 | Le service installé est accessible, avec une éventuelle authentification. | 8 | **Historique**. Démarrer et vérifier service authentifié autorisé. |
| C8.02 | Le service est configuré correctement, il répond aux besoins fonctionnels et aux contraintes techniques du projet. | 8 | **Historique**. Comparer configuration effective aux exigences. |
| C8.03 | Le monitorage disponible du service est opérationnel. | 8 | **Configuration**. Observer monitorage vivant du service. |
| C8.04 | La documentation couvre la gestion des accès à la solution, les procédures d’installation et de test, les éventuelles dépendances et interconnexions avec d’autres solutions, les données impliquées dans l’utilisation de la solution. | 8, 9 | **Configuration**. Rejouer installation/tests et inventorier dépendances/données. |
| C8.05 | La documentation est communiquée aux parties prenantes dans un format qui respecte les recommandations d’accessibilité (par exemples celles de l’association Valentin Haüy3ou de Atalan - AcceDe4). | 9 | **Incomplet**. Partager documentation accessible, preuve de lecture consentie. |

## E3 — C9 : API du modèle

Sources : P05, P07, L3. Référentiel complémentaire : S03 p. 10–11.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C9.01 | L’API restreint l’accès au modèle d’intelligence artificielle avec un moyen d’authentification. | 9 | **Historique**. Tester accès anonyme/authentifié/rôles/expiration sur vraie session. |
| C9.02 | L’API permet l’accès aux fonctions du modèle, comme attendu selon les spécifications. | 9 | **Historique**. Comparer sorties nominales et erreurs au contrat. |
| C9.03 | Les recommandations de sécurisation d’une API du top 10 OWASP sont intégrées quand nécessaires. | 9 | **Configuration**. Analyse OWASP point par point et tests justifiés. |
| C9.04 | Les sources sont versionnées et accessibles depuis un dépôt Git distant. | 9 | **Configuration**. Vérifier dépôt distant et SHA API. |
| C9.05 | Les tests couvrent tous les points de terminaison dans le respect des spécifications. | 9, 10 | **Configuration**. Inventorier endpoints puis relier chacun aux tests. |
| C9.06 | Les tests s’exécutent sans bug. | 10 | **Historique**. Rejouer suite cible, rapport passed/failed/skipped. |
| C9.07 | Les résultats des tests sont correctement interprétés. | 10 | **Historique**. Commenter assertions, mocks, skips et limites. |
| C9.08 | La documentation couvre l’architecture et tous les points de terminaisons de l’API. | 10 | **Configuration**. Contrôler architecture et exhaustivité des routes documentées. |
| C9.09 | La documentation couvre les règles d’authentification et/ou d’autorisation d’accès à l’API. | 10 | **Configuration**. Vérifier règles documentées et restrictions réelles. |
| C9.10 | La documentation et l’API respectent les standards d’un modèle choisi (par exemple Open API*). | 10 | **Configuration**. Valider conformité OpenAPI exportée. |
| C9.11 | La documentation est communiquée dans un format qui respecte les recommandations d’accessibilité (par exemple celles de l’association Valentin Haüy ou de Microsoft). | 10 | **Incomplet**. Partager documentation accessible et vérifier lecture. |

## E3 — C10 : Intégration applicative

Sources : P03, P07, L3. Référentiel complémentaire : S03 p. 11–12.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C10.01 | L’application de départ est installée et fonctionnelle en environnement de développement. | 10 | **Historique**. Installation propre de l’application de départ. |
| C10.02 | La communication avec l’API depuis l’application fonctionne. | 10 | **Historique**. Recette navigateur→API réelle. |
| C10.03 | Les éventuelles étapes d’authentification et de renouvellement de l’authentification (expiration des jetons par exemple) sont intégrées correctement en suivant la documentation de l’API. | 11 | **Configuration**. Tester expiration/révocation et renouvellement prévu. |
| C10.04 | Tous les points de terminaison de l’API concernés par le projet sont intégrés à l’application selon les spécifications fonctionnelles et techniques. | 11 | **Configuration**. Matrice endpoints utilisés→parcours et assertions. |
| C10.05 | Les adaptations d’interfaces nécessaires et en accord avec les spécifications sont intégrées à l’application. | 11 | **Configuration**. Comparer interfaces et spécifications acceptées. |
| C10.06 | Les tests d’intégration couvrent tous les points de terminaison exploités. | 11 | **Configuration**. Cartographier tests pour tous endpoints consommés. |
| C10.07 | Les tests s’exécutent en totalité : il n’y a pas de bug dans les programmes des tests en eux-mêmes. | 11 | **Historique**. Rejouer tests intégrés, aucun skip présenté comme succès. |
| C10.08 | Les résultats des tests sont correctement interprétés. | 11 | **Historique**. Interpréter résultats par environnement et périmètre. |
| C10.09 | Les sources sont versionnées et accessibles depuis le dépôt Git de l’application. | 11 | **Configuration**. Vérifier version et accès distant du frontend. |

## E3 — C11 : Monitorage du modèle

Sources : P06, L3. Référentiel complémentaire : S03 p. 12–14.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C11.01 | Les métriques faisant l’objet du monitorage du modèle sont expliquées sans erreur d’interprétation. | 11 | **Configuration**. Expliquer PSI/KS/scores non calibrés, pas précision sans labels. |
| C11.02 | Le ou les outils pour l’intégration du monitorage du modèle sont adaptés au contexte et aux contraintes techniques du projet. | 12 | **Configuration**. Motiver outils et contraintes de monitorage. |
| C11.03 | Au moins un vecteur de restitution des métriques évaluées, en temps réel, est proposé (dashboard, feuille de calcul, etc). | 12 | **Configuration**. Restituer métriques scorer vivant, pas compteur API seul. |
| C11.04 | Les enjeux d’accessibilité, pour toutes les parties prenantes du projet, sont pris en compte lors de la sélection de l’outil de restitution | 12 | **Configuration**. Contrôler accessibilité du vecteur avec utilisateurs concernés. |
| C11.05 | La chaîne de monitorage est d’abord testée dans un bac à sable ou environnement de test dédié. | 12 | **Historique**. Rejouer bac à sable et conserver traces expurgées. |
| C11.06 | La chaîne de monitorage est en état de marche. Les métriques visées sont effectivement évaluées et restituées. | 12 | **Historique**. Relier collecte→calcul→restitution effectifs. |
| C11.07 | Les sources sont versionnées et accessibles depuis un dépôt Git distant | 12 | **Configuration**. Vérifier SHA et accès distant. |
| C11.08 | La documentation technique de la chaîne de monitorage couvre la procédure d’installation de la chaîne, de configurations, et d’utilisation du monitorage à destination des équipes techniques | 12 | **Configuration**. Reproduire installation/configuration/utilisation. |
| C11.09 | La documentation est communiquée dans un format qui respecte les recommandations d’accessibilité (par exemple celles de l’association Valentin Haüy ou de Microsoft). | 12, 13 | **Incomplet**. Partager réellement support accessible. |

## E3 — C12 : Tests du modèle

Sources : P05, P07, L3. Référentiel complémentaire : S03 p. 14–15.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C12.01 | L’ensemble des cas à tester sont listés et définis : la partie du modèle visée par le test, le périmètre du test et la stratégie de test. | 13 | **Configuration**. Définir cas données/préparation/train/évaluation et frontière temporelle. |
| C12.02 | Les outils de test (framework, bibliothèque, etc.) choisis sont cohérents avec l’environnement technique du projet. | 13 | **Configuration**. Justifier frameworks et environnement compatible. |
| C12.03 | Les tests sont intégrés et respectent la couverture souhaitée établie. | 13 | **Configuration**. Définir couverture souhaitée puis mesurer ; pas pourcentage jury. |
| C12.04 | Les tests s'exécutent sans problème technique en environnement de test. | 13 | **Historique**. Rejouer tests du modèle précisément identifié. |
| C12.05 | Les sources sont versionnées et accessibles depuis un dépôt Git distant (DVC, Gitlab…). | 13 | **Configuration**. Vérifier code/données versionnés et accès distant. |
| C12.06 | La documentation couvre la procédure d’installation de l’environnement de test, les dépendances installées, la procédure d’exécution des tests et de calcul de la couverture. | 13 | **Configuration**. Documenter installation, exécution et calcul de couverture. |
| C12.07 | La documentation est communiquée dans un format qui respecte les recommandations d’accessibilité (par exemple celles de l’association Valentin Haüy ou de Microsoft). | 13 | **Incomplet**. Partager documentation accessible. |

## E3 — C13 : Livraison continue du modèle

Sources : P05, L3. Référentiel complémentaire : S03 p. 15–16.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C13.01 | La documentation pour l’utilisation de la chaîne couvre toutes les étapes, les tâches et tous les déclencheurs disponibles. | 14 | **Configuration**. Décrire déclencheur manuel et toutes étapes réelles. |
| C13.02 | Les déclencheurs sont intégrés comme préalablement définis. | 14 | **Configuration**. Déclencher workflow autorisé au SHA choisi. |
| C13.03 | Le ou les fichiers de configuration de la chaîne sont correctement reconnus et exécutés par le système selon les déclencheurs configurés. | 14 | **Configuration**. Conserver run et étapes effectivement exécutées. |
| C13.04 | L’étape de test des données est intégrée à la chaîne et s’exécute sans erreur. | 14 | **Historique**. Archiver tests données dans la même chaîne. |
| C13.05 | La ou les étapes de test, d'entraînement et de validation du modèle sont intégrées à la chaîne et s'exécutent sans erreur. | 14 | **Historique**. Archiver entraînement/validation du même artefact. |
| C13.06 | Les sources de la chaîne sont versionnées et accessibles depuis le dépôt Git distant du projet | 14 | **Configuration**. Vérifier version et accès distant de la chaîne. |
| C13.07 | La documentation de la chaîne de livraison continue couvre la procédure d’installation, de configuration et de test de la chaîne | 14 | **Configuration**. Rejouer procédure dans environnement dédié. |
| C13.08 | La documentation est communiquée dans un format qui respecte les recommandations d’accessibilité (par exemple celles de l’association Valentin Haüy ou de Microsoft). | 14 | **Incomplet**. Partager documentation accessible. |

## E4 — C14 : Analyse du besoin

Sources : P02, P03, L4. Référentiel complémentaire : S03 p. 16–17.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C14.01 | La modélisation des données respecte un formalisme : Merise, entités-relations, etc. | 15 | **Incomplet**. Compléter modèle formalisé et revue métier. |
| C14.02 | La modélisation des parcours utilisateurs respecte un formalisme : schéma fonctionnel, wireframes, etc. | 15 | **Incomplet**. Valider parcours nominaux et alternatives. |
| C14.03 | Chaque spécification fonctionnelle couvre le contexte, les scénarios d’utilisation et les critères de validation. | 15 | **Incomplet**. Contexte/scénarios/acceptation pour chaque story. |
| C14.04 | Les objectifs d’accessibilités sont directement intégrés aux critères d’acceptation des user stories. | 15 | **Incomplet**. Inscrire objectifs accessibilité dans chaque acceptation. |
| C14.05 | Les objectifs d’accessibilité sont formulés en s’appuyant sur un des standards d'accessibilité : WCAG, RG2AA, etc. | 15 | **Incomplet**. Rattacher objectifs à critères WCAG/RGAA explicites. |

## E4 — C15 : Conception technique

Sources : P02, P03, L4. Référentiel complémentaire : S03 p. 17.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C15.01 | Les spécifications techniques rédigées couvrent l’architecture de l’application, ses dépendances et son environnement d’exécution (langage de programmation, framework, outils, etc). | 15 | **Incomplet**. Actualiser architecture, dépendances et runtime au SHA. |
| C15.02 | Les éventuels services (PaaS, SaaS, etc) et prestataires ayant une démarche éco-responsable sont favorisés lors des choix techniques. | 16 | **Incomplet**. Comparer justificatifs environnementaux disponibles. |
| C15.03 | Les flux de données impliqués dans l’application sont représentés par un diagramme de flux de données. | 16 | **Incomplet**. Diagramme complet fichiers/DB/logs/exports/modèles et frontières. |
| C15.04 | La preuve de concept est accessible et fonctionnelle en environnement de pré-production. | 16 | **Incomplet**. POC fonctionnelle en préproduction isolée, pas mode démo. |
| C15.05 | La conclusion à l’issue de la preuve de concept donne un avis précis permettant une prise de décision sur la poursuite du projet. | 16 | **Incomplet**. Décision humaine go/no-go datée sur résultats, pas engagement inventé. |

## E4 — C16 : Coordination agile

Sources : P09, L4. Référentiel complémentaire : S03 p. 18.

PR #1 est une trace réelle de revue du catalogue. Elle ne prouve aucun des quatre attendus de conduite collective sur toute la durée du projet. Historique collectif **non audité**, non reconstruit.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C16.01 | Les cycles, les étapes de chaque cycle, les rôles, les rituels et les outils de la méthode agile appliquée sont respectés dans sa mise en place et tout au long du projet. | 16 | **Incomplet**. Recueillir pratiques réellement observées, pas cérémonies reconstruites. |
| C16.02 | Les outils de pilotage (tableau kanban, burndown chart, backlog, etc.) sont disponibles dans les conditions prévues par la méthode appliquée. | 16 | **Incomplet**. Outil partagé, historique et conditions d’accès réels. |
| C16.03 | Les objectifs et les modalités des rituels sont partagés à toutes les parties prenantes et rappeler si besoin. | 16 | **Incomplet**. Partager réellement objectifs/modalités des rituels. |
| C16.04 | Les éléments de pilotage sont rendus accessibles à toutes les parties du projet et ce tout au long du projet, en accord avec les recommandations de la méthode de gestion de projet appliquée. | 16, 17 | **Incomplet**. Établir disponibilité historique du pilotage pour parties concernées. |

## E4 — C17 : Composants et interfaces

Sources : P03, P07, L4. Référentiel complémentaire : S03 p. 18–19.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C17.01 | L’environnement de développement installé respecte les spécifications techniques du projet. | 17 | **Configuration**. Installer environnement conforme et versions relevées. |
| C17.02 | Les interfaces sont intégrées et respectent les maquettes. | 17 | **Configuration**. Comparer rendu aux maquettes approuvées. |
| C17.03 | Les comportements des composants d’interface (validation formulaire, animations, etc.) et la navigation respectent les spécifications fonctionnelles. | 17 | **Configuration**. Recette formulaires/navigation/erreurs et clavier. |
| C17.04 | Les composants métier sont développés et fonctionnent comme prévu par les spécifications techniques et fonctionnelles. | 17 | **Configuration**. Tests métier et résultats comparés aux exigences. |
| C17.05 | La gestion des droits d’accès à l’application ou à certains espaces de l’application est développée et respecte les spécifications fonctionnelles. | 17 | **Configuration**. Vérifier droits sur vraie session et persistance. |
| C17.06 | Les flux de données sont intégrés dans le respect des spécifications techniques et fonctionnelles. | 17 | **Configuration**. Tracer flux de bout en bout et erreurs. |
| C17.07 | Les développements sont réalisés dans le respect des bonnes pratiques d’éco-conception d’une application (Les recommandations d’éco-index ou Green IT par exemple) | 17 | **Configuration**. Audit écoconception avec mesures contextualisées. |
| C17.08 | Les préconisations du top 10 d’OWASP sont implémentées dans l’application quand nécessaire. | 17, 18 | **Configuration**. Revue OWASP et contrôles applicables. |
| C17.09 | Des tests d’intégration ou unitaires couvrent au moins les composants métier et la gestion des accès. | 18 | **Historique**. Cartographier puis rejouer tests métier/accès. |
| C17.10 | Les sources sont versionnées et accessibles depuis un dépôt Git distant. | 18 | **Configuration**. Vérifier version et accès distant. |
| C17.11 | La documentation technique couvre l’installation de l’environnement de développement, l’architecture applicative, les dépendances, l’exécution des tests. | 18 | **Configuration**. Reproduire documentation installation/architecture/tests. |
| C17.12 | La documentation est communiquée dans un format qui respecte les recommandations d’accessibilité (par exemple celles de l’association Valentin Haüy ou de Microsoft). | 18 | **Incomplet**. Partager et contrôler accessibilité documentaire. |

## E4 — C18 : Intégration continue

Sources : P10, P11, P07, L4. Référentiel complémentaire : S03 p. 20.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C18.01 | La documentation pour l’utilisation de la chaîne couvre les outils, toutes les étapes, les tâches et tous les déclencheurs de la chaîne. | 18 | **Configuration**. Confronter documentation aux six jobs actuels et déclencheurs. |
| C18.02 | Un outil de configuration et d'exécution d’une chaîne d’intégration continue est sélectionné de façon cohérente avec l’environnement technique du projet. | 18 | **Configuration**. Justifier GitHub Actions par environnement. |
| C18.03 | La chaîne intègre toutes les étapes nécessaires et préalables à l'exécution des tests de l’application (build, configurations…). | 18 | **Configuration**. Vérifier préalables et séparation contexte build Web. |
| C18.04 | La chaîne exécute les tests de l’application disponibles lors de son déclenchement. | 19 | **Historique**. Archiver run CI 34360646172 et tests/skips au même SHA. |
| C18.05 | Les configuration sont versionnées avec les sources du projet d’application, sur un dépôt Git distant. | 19 | **Configuration**. Vérifier SHA et accès distant aux configurations. |
| C18.06 | La documentation de la chaîne d’intégration continue couvre la procédure d’installation, de configuration et de test de la chaîne. | 19 | **Configuration**. Reproduire procédure de configuration et tests CI. |
| C18.07 | La documentation est communiquée dans un format qui respecte les recommandations d’accessibilité (par exemple celles de l’association Valentin Haüy ou de Microsoft). | 19 | **Incomplet**. Partager documentation accessible. |

## E4 — C19 : Livraison application

Sources : P10, P11, P06, L4. Référentiel complémentaire : S03 p. 21–22.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C19.01 | La documentation pour l’utilisation de la chaîne couvre toutes les étapes de la chaîne, les tâches et tous les déclencheurs disponibles. | 19 | **Configuration**. Documenter CI→build→livraison et promotion désactivée. |
| C19.02 | Le ou les fichiers de configuration de la chaîne sont correctement reconnus et exécutés par le système. | 19 | **Historique**. Conserver résultat réel du workflow ; échec non masqué. |
| C19.03 | La ou les étapes de packaging (compilation, minification, build de containers, etc.) de l’application sont intégrées à la chaîne et s'exécutent sans erreur. | 19 | **Incomplet**. Après revue/fusion correctif, build complet distant réussi. |
| C19.04 | L’étape de livraison (pull request par exemple) est intégrée et exécutée une fois la ou les étapes de packaging validées. | 20 | **Incomplet**. Prouver livraison après packaging validé, pas deploy skipped. |
| C19.05 | Les sources de la chaîne sont versionnées et accessibles depuis le dépôt Git distant du projet d’application. | 20 | **Configuration**. Vérifier version et accès distant. |
| C19.06 | La documentation de la chaîne de livraison continue couvre la procédure d’installation, de configuration et de test de la chaîne. | 20 | **Configuration**. Rejouer procédure sur cible autorisée et rollback compatible. |
| C19.07 | La documentation est communiquée dans un format qui respecte les recommandations d’accessibilité (par exemple celles de l’association Valentin Haüy ou de Microsoft). | 20 | **Incomplet**. Partager documentation accessible. |

## E5 — C20 : Surveillance application

Sources : P06, L5. Référentiel complémentaire : S03 p. 22.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C20.01 | La documentation liste les métriques et les seuils et valeurs d’alerte pour chaque métrique à risque. | 20 | **Configuration**. Définir seuils par risque et métriques opérationnelles. |
| C20.02 | La documentation explicite les arguments en faveur des choix techniques pour l’outillage du monitorage de l’application. | 20 | **Configuration**. Justifier choix de collecte/journalisation/restitution. |
| C20.03 | Les outils (collecteurs, journalisation, agrégateurs, filtres, dashboard, etc.) sont installés et opérationnels à minima en environnement local. | 20 | **Historique**. Installer et observer chaîne complète au moins locale. |
| C20.04 | Les règles de journalisation sont intégrées aux sources de l’application, en fonction des métriques à surveiller. | 21 | **Configuration**. Vérifier journalisation intégrée et minimisation des données. |
| C20.05 | Les alertes sont configurées et en état de marche, en fonction des seuils préalablement définis. | 21 | **Historique**. Déclencher puis recevoir alerte par canal approuvé. |
| C20.06 | La documentation couvre la procédure d’installation et de configuration des dépendances pour l’outillage du monitorage de l’application. | 21 | **Configuration**. Rejouer installation/configuration des dépendances. |
| C20.07 | La documentation est communiquée dans un format qui respecte les recommandations d’accessibilité (par exemple celles de l’association Valentin Haüy ou de Microsoft). | 21 | **Incomplet**. Partager support accessible. |

## E5 — C21 : Résolution des incidents

Sources : P08, P11, X03, L5. Référentiel complémentaire : S03 p. 23.

| ID | Exigence exacte (S06) | Page | Statut de preuve / prochaine preuve |
|---|---|---|---|
| C21.01 | La ou les causes du problème sont identifiées correctement. | 21 | **Historique**. Distinguer cause locale reproduite et cause distante non confirmée. |
| C21.02 | Le problème est reproduit en environnement de développement. | 21 | **Historique**. Rejouer état avant correctif sur environnement éphémère autorisé. |
| C21.03 | La procédure de débogage du code est documentée depuis l’outil de de suivi. | 21 | **Incomplet**. Lien outil de suivi authentique, pas ticket reconstruit. |
| C21.04 | La solution documentée explicite chaque étape de la résolution et de son implémentation. | 21 | **Historique**. Conserver étapes diagnostic→correctif→non-régression. |
| C21.05 | La solution est versionnée dans le dépôt Git du projet d’application (par exemple avec une merge request). | 21, 22 | **Historique**. Relier solution au commit et revue, puis rejeu après intégration. |
