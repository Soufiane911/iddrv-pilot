# C6/C7 — état documentaire et protocole de comparaison

Consultation du 9 septembre 2026, **pas une veille historique ni un benchmark exécuté**. Besoin proposé : signaler une dérive process contextualisée, exposable dans l'application existante, avec provenance/version et exploitation sobre. Pas de diagnostic certain de rebut, pas de RAG ou nouveau simulateur. Budget, seuils de latence, coût et qualité doivent être approuvés par le commanditaire.

## Sources effectivement lues et limites

| Source consultée aujourd'hui | Auteur/provenance | Ce qu'elle permet de dire | Limite |
|---|---|---|---|
| `models/process_drift_hdt_v1.meta.json` sur base 01fcb4f | Artefact du dépôt IDDRV ; auteur individuel non vérifié | Features volatilités, horizon 20 cycles, environnement déclaré Python 3.13.9/scikit-learn 1.7.2/joblib 1.5.2 | Métriques déclarées, non recalculées ; aucun résultat nouveau |
| `backend/app/schemas.py` même base | Dépôt IDDRV | Contrats API typés, agrégats bornés annoncés | Pas mesure de fonctionnement réseau |
| `Preuve-manquante/organisation/veille_2026-09-08.md`, dépôt principal en lecture seule | Dossier local, compte rendu daté du 8 septembre | Décrit une consultation CNIL et scikit-learn 1.7 | Lecture secondaire seulement ; ni URLs revalidées ni partage établi aujourd'hui |
| R7–9 / G6–8, extraits officiels | Simplon, RNCP37827 | Attendus veille/benchmark et cadence minimale 1h/semaine | Pas une recommandation technologique |

Tentatives de consultation primaire via web_fetch : `https://scikit-learn.org/stable/modules/outlier_detection.html` et `https://docs.seldon.ai/seldon-core-2` : **échec fetch**. Ces pages ne sont donc pas présentées comme lues. Ne pas reprendre les affirmations d'un fournisseur non consulté. La date de consultation locale n'est pas la date de publication d'une source externe.

## Comparaison préparatoire, non équivalente au benchmark final

| Candidat | Dérive/contextualisation | Intégration et exploitation | Prérequis / limites | Écoresponsabilité |
|---|---|---|---|---|
| Service IDDRV existant, HDT/IsolationForest | Features et horizon présents dans meta ; pertinence industrielle à valider | Contrats existants, artefact versionné ; service non exécuté dans ce lot | Environnement compatible, artefact de confiance, données contextualisées ; pas diagnostic causal | Aucune mesure énergie/CO2 disponible ; ne pas déduire sobriété du mot local |
| Seldon Core 2 | Non étudié, documentation non accessible ici | Non évalué | Accès source primaire et étude coût/complexité avant décision ; ne pas installer pour ce dossier | Inconnue |
| Service cloud propriétaire de détection d'anomalies | Non étudié | Non évalué | Besoin, budget, confidentialité/transferts et disponibilité fournisseur non établis ; exclu de décision actuelle | Inconnue |
| Service LLM/RAG | Non étudié, hors besoin retenu | Hors périmètre autorisé | Écarté : retrieval/conversation ne répond pas au contrat de dérive visé | Non évaluée |

Conclusion provisoire : conserver l'existant comme candidat de référence évite une migration non justifiée ; ce n'est pas une supériorité prouvée. **Pas de recommandation fournisseur définitive** avant consultation primaire et essais comparables. Avantage documenté : intégration déjà présente ; inconvénient : validité industrielle, latence et impact environnemental non établis ici. Mesurer même jeu autorisé, même fenêtre, matériel, versions, qualité, latence p50/p95, mémoire et énergie mesurée (outil/périmètre/incertitude), puis arbitrer sans inventer CO2 ni labels fournisseur.

## Organisation proposée, correction d'un écart documentaire réel

La proposition locale du 8 septembre indiquait trente minutes hebdomadaires : elle est **insuffisante** face à R7/G6. Proposition corrigée : **au moins une heure par semaine**, par exemple 20 min collecte, 20 qualification/recoupement, 20 synthèse/partage. Aucun créneau tenu n'est inventé et le fichier local n'est pas modifié.

Agrégation proposée : flux RSS officiels lorsque disponibles et liste versionnée d'URLs en Markdown, sans nouvel abonnement avant budget approuvé. Pour chaque entrée : auteur et compétence, intérêts possibles (documentation fournisseur non neutre), date/version, structure, sources secondaires de confiance, accessibilité réellement contrôlée, décision et fichier impacté. Thèmes : détection de dérive, persistance sécurisée, données personnelles, accessibilité. Partage à organiser en HTML/Markdown lisible au clavier et lecteur d'écran, titres hiérarchisés/liens explicites ; conserver date, destinataires consentants et retour réel. Aucun message ni réunion réalisés par ce lot.
