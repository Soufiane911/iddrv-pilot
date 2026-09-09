# Organisation prospective à approuver

Proposition écrite le 9 septembre 2026; aucune invitation ou séance créée. Ne pas l'appliquer rétroactivement. C6 exige au moins une heure hebdomadaire; la proposition locale de trente minutes est insuffisante, sans modification de son archive.

## Veille : calendrier futur

Fuseau proposé **Europe/Paris**. Première séance proposée le **vendredi 11 septembre 2026, 14 h–15 h**, puis vendredis 18 et 25 septembre, 2 octobre aux mêmes heures; poursuite hebdomadaire à confirmer au bilan du 2 octobre. `FREQ=WEEKLY;BYDAY=FR`, durée planifiée 60 minutes. Ces dates sont une planification documentaire conditionnelle, pas des événements de calendrier envoyés ni une durée effectuée.

- 20 minutes : sélectionner/collecter les nouveautés pertinentes.
- 20 minutes : qualifier auteur, version, date, intérêts, accessibilité et recoupement.
- 20 minutes : synthétiser l'impact projet, discuter une recommandation et préparer son partage.
- Si une séance manque, enregistrer « non tenue », replanifier explicitement sans copier une durée prévue en durée réalisée. Mesurer début/fin et durée effective lors des futures séances seulement.

Responsable de collecte proposé : candidat, acceptation à recueillir. Relecteur humain technique et interlocuteur métier/tuteur : à identifier et solliciter, pas présentés comme membres existants. Responsable de traitement : à identifier pour les décisions RGPD; une personne technique ne décide pas seule d'une obligation légale.

## Agrégation proportionnée et sources

Préférer le dispositif Feedly **déjà documenté par captures** à l'installation d'un nouvel outil. Aucun abonnement créé ici. Coût/licence et droit de partage réels inconnus : faire confirmer par le titulaire; enveloppe proposée pour ce lot documentaire : zéro achat supplémentaire. Si accès partagé indisponible, liste versionnée d'URLs et collecte manuelle suffisent comme solution de repli, pas comme preuve de flux RSS actifs.

Axes existants : technique (PostgreSQL, AWS ML/IoT, InfluxData, arXiv), réglementaire (CNIL, EDPB, NIST, LIBE, portail d'analyse AI Act non officiel), stratégique (presse industrielle). Ne pas assimiler prépublication à résultat validé, portail d'analyse à texte officiel, NIST à obligation européenne ou deux flux AWS à deux sources indépendantes. Garder seulement articles liés à injection molding, process drift, time series, OPC UA, données et accessibilité. Les quatre URL primaires de la séance sont une liste consultable dans `index.json`, pas des endpoints RSS supposés.

Pour chaque prochaine sélection : statut tendance/opportunité/menace/signal faible **argumenté**, URL canonique, auteur/compétence, intérêt possible, date/version, accès ou échec, résumé original, recoupement indépendant ou son absence, recommandation, décision humaine et preuve du partage. L'actualité d'une documentation versionnée se juge aussi sur le runtime ciblé, pas seulement sur une date récente.

## Pilotage Kanban léger, pas un Scrum historique

Un cycle proposé dure une semaine : sélection des tâches → réalisation isolée → revue/test → décision d'intégration → bilan/retour métier. [Backlog borné](backlog.json) de 9 lots, sans points ni vélocité inventés. Colonnes proposées : à valider, prêt, en cours, en revue, bloqué, terminé avec preuve. Limite de travail en cours : deux lots techniques maximum, pas d'édition concurrente du même périmètre. Toutes les entrées actuelles sont « à valider »; la présence des pièces de main ne clôt aucun lot.

Rôles **à accepter** : candidat (pilotage et préparation), commanditaire/utilisateur (besoin/acceptation), relecteur technique humain (risques/contrats), responsable exploitation (rollout/rollback), responsable de traitement (RGPD). Les mêmes personnes peuvent cumuler des rôles si explicité, sans inventer une équipe. Agent IA : assistance de lecture/rédaction/tests autorisés, sans vote métier ni validation professionnelle indépendante.

Rituels proposés, hors heure de veille :

- Lundi 9 h–9 h 15 à partir du 14 septembre : sélection hebdomadaire, objectifs et dépendances, un pilote à désigner.
- À chaque blocage réel : mise à jour asynchrone dans le backlog, cause/source, impact, décision attendue et propriétaire; aucune fausse réunion quotidienne.
- Vendredi 15 h–15 h 20 à partir du 11 septembre : revue des preuves produites et mini-rétrospective, aucun résultat sans commit/run/scénario; retour des participants réellement présents.
- Avant chaque intégration : périmètre convenu, PR proposée par une personne autorisée, relecture, checks attachés au bon SHA, décision explicite; après fusion, contrôle du commit intégré. PR numéro 1 montre un cycle versionné/CI, mais pas de revue humaine approuvée.

Contexte MLOps : l'identité du modèle, des données, des features, du seuil et des résultats doit suivre le ticket/PR. Les résultats de recherche ne remplacent pas le runtime sans packaging, replay causal, validation et plan de retour. Un imprévu tel qu'une confirmation expérimentale absente reste bloquant, pas effacé par une fusion documentaire.

## Disponibilité et partage à valider

Canal proposé : lien vers Markdown rendu du dépôt pour preuves non sensibles; canal privé approuvé pour décisions internes. Ne pas joindre d'identifiants de compte, tokens, logs personnels ou captures Feedly nominatives. Pour le JSON, fournir aussi les explications françaises de ce dossier. Vérifier le rendu réel, clavier, zoom, titres, liens et compréhension avec les destinataires.

Avant démarrage, l'utilisateur doit **(1)** confirmer noms/rôles et accord des personnes, **(2)** accepter ou remplacer les créneaux sans descendre sous 1 h de veille hebdomadaire, **(3)** choisir canal/budget et vérifier l'accès de chaque partie, **(4)** valider priorités et critères de fin, **(5)** envoyer les modalités et conserver envoi/retours datés. L'agent ne réalise aucune de ces actions au nom d'autrui. Renseigner un compte rendu contemporain à chaque séance tenue et chaque changement; un partage public ne prouve pas automatiquement l'accès effectif des personnes visées.
