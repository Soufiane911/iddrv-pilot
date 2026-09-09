# Conducteur proposé pour les cinq épreuves

## Statut et arbitrage des modalités

Ce conducteur est une **proposition à répéter**, pas une soutenance effectuée. Il ne modifie ni le rapport déposé ni les livrets historiques. Le candidat doit distinguer sa contribution personnelle, le code produit avec assistance et les vérifications réellement réalisées.

Références exactes : S05 p.12 dispose « La présentation orale dure au total 90 minutes », dont présentation, démonstrations et échange sur rapports **80 min**, puis questions **10 min**. Les durées détaillées des blocs sur la même page donnent E1 **15**, E2 **15**, E3 **20**, E4 **20**, E5 **10** minutes. Elles totalisent 80 minutes. S06 décrit les modalités d’évaluation mais **ne prescrit pas ces durées** : E1 p.2, E2 p.6, E3 p.9, E4/E5 p.15.

**Conflit à faire arbitrer avant répétition finale :** S01 slide 7 affiche E3 15 min et un total détaillé de 85 min, tout en annonçant 90 ; slide 10 affiche E3 20 min. La V6 externe (X04/X05) consigne une instruction candidat de 75+10, E3 15. Une instruction consignée n’est pas une modification officielle des modalités. Ne pas inventer cinq minutes supplémentaires ni ajouter dix minutes de questions après chaque épreuve pour un passage du titre entier. Les images de l’annexe S05 p.15–17 n’ont pas été auditées visuellement ; demander confirmation écrite au responsable de session du déroulé applicable.

S01 slide 7 indique rapports E1 2–5 pages, E2/E3/E4 15–20 pages et documentation E5 2–5 pages. S05 p.7–11 et S06 prescrivent des rapports individuels E1–E4, documentation technique du monitorage et de résolution E5, sans ces volumes dans les passages textuels consultés. **Faire confirmer les volumes et le format de dépôt**, ne pas les attribuer à la grille.

## Plan de répétition provisoire : 80 + 10 minutes

Les budgets par épreuve viennent de S05 p.12. Les subdivisions ci-dessous sont des **choix de présentation proposés**, non des contraintes du certificateur. Démonstrations incluses dans les budgets, secours inclus également.

| Temps | Épreuve | Contenu proposé et preuves | Zone à compléter avant passage |
|---|---|---|---|
| 0–15 | E1, C1–C5 | 3 min contexte/flux ; 4 min collecte et SQL ; 3 min modèle/RGPD ; 4 min démonstration données/API ; 1 min limites. P01, P02, P03, X01. | Source autorisée, vrai import/relecture, auth et SQL métier. P01 n’est que SQLite synthétique. P12 séparé et non fusionné. |
| 15–30 | E2, C6–C8 | 4 min besoin/veille ; 6 min comparaison sourcée ; 4 min paramétrage/version ; 1 min décision et limites. P04, P05, P09, X02. | Partage de veille réel, cadence ≥1h/semaine, benchmark de services, budget et avis humain. |
| 30–50 | E3, C9–C13 | 4 min contrat/auth ; 6 min démo API et intégration ; 4 min monitorage ; 4 min tests/chaîne modèle ; 2 min limites. P05, P06, P07, P09. | Session réelle, sortie/version du modèle chargé, erreurs, run de livraison modèle. Catalogue ≠ inférence summary6. |
| 50–70 | E4, C14–C19 | 3 min besoin/stories ; 3 min architecture ; 2 min organisation et revue réelle ; 6 min parcours utilisateur ; 3 min CI ; 3 min livraison/limites. P02, P03, P07, P09–P11. | Recette persistée et accessibilité manuelle ; distinction CI verte/Delivery échouée ; revue ≠ historique collectif. |
| 70–80 | E5, C20–C21 | 2 min surveillance ; 2 min incident et reproduction ; 3 min diagnostic/correctif ; 2 min tests/non-régression ; 1 min capitalisation. P06, P08 et éventuellement P11. | Choisir un seul cas principal et ses preuves avant/après ; lien authentique outil de suivi ; complément accepté par la session. |
| 80–90 | Questions | Réponses argumentées, retour aux IDs Cx.yy et pièces exactes. | Modalités finales confirmées par responsable. |

## Démonstrations : conditions d’entrée et secours

### E1 — De la source à la donnée exposée

Proposition : montrer source synthétique clairement identifiée → normalisation/rejets → SQL → import → lecture authentifiée. P01 permet seulement les trois premières étapes et une projection SQLite validée par Pydantic, **sans endpoint HTTP**. Ne pas annoncer les étapes suivantes comme réalisées.

- Préparer : SHA de la version, source et empreinte, environnement isolé, commandes expurgées, compteurs attendus et obtenus.
- Compléter : login réel, persistance, refus anonyme/intersite, export OpenAPI et comparaison des champs/pagination.
- Secours : P01 et X01 explicitement bornés. X05 renvoie D64 à une source CSV seule ; elle ne prouve pas un import. La sélection SQLite D10 est distincte du réconciliateur applicatif.
- Arrêt : si la stack manque, présenter l’archive et ses limites, pas une réponse reconstruite.

### E3 — Contrat du modèle, limites scientifiques et livraison

Proposition : appel nominal autorisé, entrée trop courte/refus, lecture de la version, composant UI correspondant, métriques puis chaîne du **même** modèle.

- Le modèle historique reste la référence distribuée sur main. P09 catalogue quatre identités mais ne sélectionne ni n’exécute les candidats recherche.
- P13 est un moteur summary6 **non fusionné**, paquet privé ; API en chantier. Ne pas l’intégrer silencieusement à la démonstration ni aux livrets.
- Les résultats historiques du rapport, summary6 initial, mean79 confirmation01 et EWM20 développement/confirmation02 absente sont quatre contextes différents. **Aucun chiffre ML n’est transposé entre campagnes** ; montrer population, graine, artefact, phase et dénominateur avant toute métrique. Les trois graines d’un jeu ne sont pas trois jeux indépendants.
- X04 distingue API machine 152, panneau archivé 1003 et investigation 606. Ne pas fabriquer une continuité entre ces captures.
- Secours : artefact/meta/catalogue et captures nommées comme archives ; un YAML, un test unitaire et un paquet local ne prouvent pas une livraison sur cible.

### E4 — Usage, accès et livraison

Proposition : login → site autorisé → machine → information datée → examen humain → sauvegarde et relecture du retour. Inclure accès refusé, session expirée, état vide/erreur, clavier et focus.

P07 rapporte des tests navigateur en **mode démo** et des tests DB/Redis séparés : leur addition ne devient pas un parcours intégré. Contrôles accessibilité manuels et réception utilisateur restent à produire. Aucun gain de temps, témoignage, réception client ou mesure environnementale n’est inventé.

Pour CI/livraison : montrer CI main `34360646172` réussie, puis Delivery `34361237874` réellement échouée au build Web et deploy skipped. Une publication API partielle est possible. P11 rapporte une correction et un build Docker local réussi à `4b6b458d`, **non fusionnés**, pas une nouvelle livraison main réussie.

### E5 — Choisir une résolution démontrable, sans refaire l’histoire

**Cas principal proposé : P08, incident du harness E2E.** Cause locale documentée : effacement du registre des migrations avec conservation des objets, plus défauts de fixtures. Solution consignée : préserver `schema_migrations`, corriger fixtures et vérifier idempotence. Le document rapporte un avant/après réel mais non rejoué dans ce lot. Les traces éphémères originales et le lien à l’outil de suivi doivent être joints/confirmés. Ne pas attribuer avec certitude ces causes au run distant historique inaccessible.

**Alternative complémentaire : P11, build Web et rapport Delivery.** Un échec local TS2307 est reproduit, correction limitée et vrai build Docker local rapportés, mais branche non fusionnée et logs distants complets indisponibles. Réserver ce cas à une présentation explicitement postérieure au rapport et acceptée par la session.

**Ne pas substituer sans avertissement :** L5 décrit le confinement d’un fichier invalide, sans nouveau correctif versionné ni redépôt corrigé prouvé ; X03 est un exercice de refus d’artefact incompatible suivi d’un retour sain sans modification de code. X04 sépare journal du 7 août et reconstitution du 16 août, alors que L5 p.3 reprend le 7 août : incohérence historique à signaler, pas à résoudre par une chronologie inventée.

## Checklist de livraison documentaire et de passage

- [ ] Responsable de session confirme date, format, volumes, destinataire sécurisé et modalités de complément post-dépôt. **Date réelle : à renseigner**, aucune échéance absolue inventée.
- [ ] Prévoir remise au responsable suffisamment tôt pour transmission **au jury au plus tard cinq jours avant la session** : S04 p.5 et S05 p.7. Ce délai porte sur la transmission par le responsable ; il ne fixe pas à lui seul la date limite de remise du candidat.
- [ ] Confirmer la convocation : S04 p.5 prévoit minimum six semaines pour les candidats ; S01 slide 7 annonce deux semaines. Faire arbitrer, ne pas choisir silencieusement.
- [ ] Préparer convocation et pièce d’identité **privées**, jamais jointes au dépôt public (S04 p.5–6).
- [ ] Vérifier rapports individuels E1–E4 et deux documentations E5 ; citations/pages, index, liens, empreintes et statut des références externes.
- [ ] Conserver rapport/livrets historiques intacts ; compléments clairement datés et rattachés au SHA réellement présenté.
- [ ] Confirmer minutage 90 min et arbitrage E3 avant répétition ; chronométrer démonstrations avec secours.
- [ ] Préparer uniquement comptes/fixtures synthétiques et stack autorisée isolée ; aucune commande destructive sur environnement partagé.
- [ ] Vérifier lecture clavier, titres, contrastes, zoom et export PDF lisible ; ne pas assimiler ce contrôle documentaire à un audit complet du produit.
- [ ] Expurger noms, adresses, emails, tokens, cookies, chemins privés et contenus métier de captures et logs ; revue humaine avant diffusion.
- [ ] Vérifier permission de partager les sources externes et les résultats, sans copier `.venv`, modèles privés ou expériences volumineuses.
- [ ] Préparer contribution personnelle et limites ; ne pas inventer tickets, réunions, veille collective ou accords client.

S04 p.6 : acquisition d’une compétence soumise à validation de tous ses critères ; décision souveraine et collégiale du jury. Cet index ne remplace ni la grille ni cette décision.
