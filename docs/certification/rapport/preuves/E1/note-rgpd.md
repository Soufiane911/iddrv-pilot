# Note RGPD — pilote IDDRV

**Objectif :** préciser la nature des données traitées par le pilote IDDRV et
les mesures appliquées. Document de soutenance (C4), à confirmer avec le
responsable juridique du site avant déploiement.

## 1. Nature des données

Les données ingérées par IDDRV sont des **données de production industrielle** :

- **Données machine** : cycles de presse (temps, pressions, températures,
  forces, énergie), identifiants machine (`machine_erp_ref`) ;
- **Données d'ordres de fabrication** : références produit, quantités, OF,
  équipes (issue de l'ERP) ;
- **Données de qualité** : `scrap_flag`, statut de pièce, notes d'opérateur
  (libres).

Elles ne contiennent **pas** de données personnelles au sens RGPD (pas de nom,
pas d'identifiant individuel d'opérateur, pas de données biométriques) dans le
périmètre actuel du pilote. Les notes opérateur libres sont traitées comme des
données potentiellement sensibles : elles ne sont pas exposées en clair dans les
captures et ne sortent pas du périmètre on-premise.

## 2. Base de traitement

- **Intérêt légitime de l'entreprise** (art. 6.1.f RGPD) : supervision de la
  production, détection de dérive et amélioration de la qualité ;
- Les traitements sont **proportionnés** : seules les données nécessaires au
  pilotage et à la détection de dérive sont collectées.

## 3. Mesures techniques

| Mesure | Mise en œuvre IDDRV |
|---|---|
| Minimisation | Collecte ciblée des colonnes du contrat EUROMAP 77/83 ; colonnes inconnues conservées mais non exploitées |
| Pseudonymisation | Identifiants internes (site, machine) ; pas d'identifiant personne |
| Confidentialité | Stockage **on-premise** (PostgreSQL/TimescaleDB en local, DB non exposée au LAN — seule l'UI web est exposée) ; aucune donnée envoyée vers un cloud |
| Sécurité | Auth Argon2id, cookie HttpOnly, RBAC (viewer/analyst/supervisor/admin), isolation par site (404 cross-site) |
| Traçabilité | Hash SHA-256 des fichiers d'entrée, journal d'imports (passports), logs structurés |
| Rétention | Backup/restore scripts ; pas de durée de rétention définie dans le pilote (à documenter avec le site) |

## 4. Absence d'export et de LLM cloud

- **Aucune donnée d'atelier ne quitte l'infrastructure** : le diagnostic est
  déterministe et local, le modèle HDT est un artefact local (sklearn) ;
- Le recours à un LLM cloud est **explicitement écarté** pour le pilote
  (confidentialité, coût, hallucination) — voir rapport E2 ;
- En cas d'évolution (LLM/RAG), une analyse d'impact (AIPD) serait nécessaire.

## 5. Limites à assumer

- Le pilote n'a pas de registre de traitement formel ni d'AIPD : à compléter
  avec le DPO/le responsable du site avant déploiement ;
- Les données de démonstration sont **synthétiques** (simulation réaliste) ;
  aucune donnée réelle de site n'est présente dans le dépôt.

## 6. Références

- EUROMAP 77/83 (interopérabilité, pas de données personnelles)
- `docs/on-prem-runbook.md` (isolation réseau, backup/restore)
- `docs/api-v1-contract.md` (contrats d'API, isolation par site)
- `docs/certification/rapport/E2-veille-IA-C6-C8.md` (choix on-prem vs cloud)
