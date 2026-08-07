# Mapping générique d'un projet sur les 5 épreuves DEVIA

> Document de référence externe. Il ne décrit pas fidèlement les fonctionnalités
> actuellement implémentées dans IDDRV.

> **Projet** : Application web d'analyse de données métier + IA agentique + RAG  
> **Verdict** : Ce projet couvre **naturellement les 5 épreuves** comme fil rouge 🎉

---

## 🏗️ Architecture globale du projet

```
┌──────────────────────────────────────────────────────────────────────┐
│                        UTILISATEUR                                   │
│                    (navigateur web)                                   │
└──────────────┬───────────────────────────────────┬───────────────────┘
               │                                   │
               ▼                                   ▼
┌──────────────────────────┐         ┌──────────────────────────┐
│     APPLICATION WEB      │         │      AGENT IA            │
│   (React / Vue / Next)   │         │   (LangChain / CrewAI)   │
│                          │         │                          │
│  • Dashboards données    │◄───────▶│  • Orchestration tâches  │
│  • Visualisations        │         │  • Appel d'outils        │
│  • Interface chat RAG    │         │  • Raisonnement          │
└──────────┬───────────────┘         └──────────┬───────────────┘
           │                                    │
           ▼                                    ▼
┌──────────────────────────┐         ┌──────────────────────────┐
│     BACKEND / API        │         │     SYSTÈME RAG          │
│     (FastAPI / Django)   │         │                          │
│                          │         │  • Embedding docs        │
│  • API REST données      │         │  • Vector store          │
│  • Auth / RBAC           │         │    (ChromaDB / Pinecone) │
│  • Logique métier        │         │  • Retrieval + LLM       │
└──────────┬───────────────┘         └──────────┬───────────────┘
           │                                    │
           ▼                                    ▼
┌──────────────────────────┐         ┌──────────────────────────┐
│     DONNÉES MÉTIER       │         │     BASE DE DOCUMENTS    │
│                          │         │                          │
│  • PostgreSQL / MongoDB  │         │  • PDFs, rapports        │
│  • Sources externes      │         │  • Docs techniques       │
│  • Fichiers CSV/Excel    │         │  • Base de connaissances │
└──────────────────────────┘         └──────────────────────────┘

           │                                    │
           └──────────┬─────────────────────────┘
                      ▼
          ┌──────────────────────────┐
          │     MONITORING           │
          │  Prometheus + Grafana    │
          │  Logs + Alertes          │
          └──────────────────────────┘
```

---

## 📌 Épreuve E1 — Collecte, stockage et mise à disposition des données
**Rapport : 2-5 pages | 15 min | C1-C5**

### 🎯 Angle : « Comment j'ai construit le pipeline de données métier »

Tu racontes comment tu as collecté, nettoyé, stocké et exposé les données métier de l'entreprise pour alimenter à la fois l'application web ET le système RAG.

### 📄 Plan du rapport (2-5 pages)

1. **Contexte** (~0.5 page)
   - L'entreprise, les données métier existantes (nature, volume, formats)
   - Le besoin : centraliser et rendre accessibles des données dispersées

2. **Collecte automatisée** (~1 page) → *C1, C2*
   - Sources : BDD existante de l'entreprise (requêtes SQL), fichiers CSV/Excel, APIs tierces
   - Scripts Python d'extraction automatisée (ex: `sqlalchemy` + `requests` + `pandas`)
   - Planification (cron / Celery / Airflow si pertinent)

3. **Nettoyage et agrégation** (~1 page) → *C3*
   - Règles de nettoyage : doublons, formats incohérents, données manquantes
   - Homogénéisation des formats entre sources
   - Scripts de transformation (pandas / dbt)

4. **Stockage** (~1 page) → *C4*
   - Modèle conceptuel (MCD) et physique (MPD) de la BDD
   - Choix PostgreSQL / MongoDB justifié
   - Conformité RGPD (anonymisation si données sensibles, droit à l'oubli)

5. **Exposition via API** (~0.5 page) → *C5*
   - API REST (FastAPI) pour consommer les données
   - Endpoints principaux, authentification
   - Documentation Swagger auto-générée

### 💬 Ce que le jury veut entendre :
> « J'ai automatisé la collecte depuis 3 sources différentes, nettoyé les données avec des règles métier, stocké le tout dans une BDD bien modélisée et conforme RGPD, et exposé les données via une API documentée. »

---

## 📌 Épreuve E2 — Veille et services d'IA
**Rapport : 15-20 pages | 15 min | C6-C8**

### 🎯 Angle : « Comment j'ai choisi la stack IA pour le RAG et l'agent »

C'est ici que tu montres ton travail de **veille, benchmark et préconisation** pour choisir les bons outils IA.

### 📄 Plan du rapport (15-20 pages)

1. **Dispositif de veille** (~3 pages) → *C6*
   - Tes sources : Papers With Code, HuggingFace blog, arXiv, newsletters IA (The Batch, TLDR AI), communautés (Reddit r/MachineLearning, Discord)
   - Organisation : veille hebdomadaire, curation dans Notion/Obsidian
   - Partage avec l'équipe (présentations internes, Slack/Teams)

2. **Problématique** (~2 pages)
   - « L'entreprise souhaite un assistant intelligent capable de répondre aux questions des utilisateurs en s'appuyant sur les documents et données internes. Quel stack IA choisir ? »
   - Contraintes : budget, hébergement (cloud vs on-prem), confidentialité des données, latence

3. **Benchmark des solutions** (~6 pages) → *C7*

   **a) Choix du LLM :**
   | Critère | GPT-4o (OpenAI) | Mistral Large | Claude 3.5 | Llama 3 (local) |
   |---------|----------------|---------------|-------------|-----------------|
   | Performance | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
   | Coût | $$$ | $$ | $$$ | $ (infra) |
   | Confidentialité | ⚠️ Cloud | ⚠️ Cloud | ⚠️ Cloud | ✅ On-prem |
   | Latence | Rapide | Rapide | Rapide | Variable |

   **b) Choix du framework RAG :**
   | Critère | LangChain | LlamaIndex | Haystack |
   |---------|-----------|------------|----------|
   | Maturité | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
   | Flexibilité | Très élevée | Élevée | Moyenne |
   | Agent support | ✅ Natif | Partiel | Partiel |

   **c) Choix du vector store :**
   | Critère | ChromaDB | Pinecone | Weaviate | pgvector |
   |---------|----------|----------|----------|----------|
   | Hébergement | Local | Cloud | Les deux | Extension PG |
   | Coût | Gratuit | Payant | Freemium | Gratuit |

4. **Préconisation** (~2 pages) → *C7*
   - Recommandation argumentée (ex: Mistral + LangChain + ChromaDB pour confidentialité + coût)
   - Justification technique et business

5. **Installation et configuration** (~4 pages) → *C8*
   - Étapes d'installation pas à pas
   - Configuration du LLM (API keys, paramètres)
   - Configuration du vector store
   - Test de validation (requête de bout en bout)
   - Captures d'écran / extraits de code

### 💬 Ce que le jury veut entendre :
> « J'ai structuré une veille rigoureuse, identifié et comparé objectivement les solutions IA du marché, et formulé une recommandation technique argumentée en tenant compte des contraintes de l'entreprise. »

---

## 📌 Épreuve E3 — Intégration du modèle/service d'IA
**Rapport : 15-20 pages | 15 min + DÉMO | C9-C13**

### 🎯 Angle : « Comment j'ai construit et intégré le service RAG + l'agent IA »

Tu montres comment tu as encapsulé le système RAG dans une API, intégré l'agent IA dans l'application, et mis en place le monitoring et le CI/CD.

### 📄 Plan du rapport (15-20 pages)

1. **API REST du service RAG** (~4 pages) → *C9*
   - Architecture de l'API (FastAPI)
   - Endpoints : `/chat`, `/index-document`, `/search`, `/agent/task`
   - Sécurisation (JWT, rate limiting)
   - Documentation OpenAPI
   - Gestion des erreurs, retries

2. **Intégration dans l'application web** (~4 pages) → *C10*
   - Interface chat dans l'app (composant React/Vue)
   - Intégration de l'agent : boutons d'actions assistées (« Analyser ces données », « Générer un rapport »)
   - Gestion du contexte conversationnel
   - Accessibilité (WCAG)
   - UX : streaming des réponses, indicateurs de chargement

3. **Monitorage du modèle** (~4 pages) → *C11*
   - Métriques surveillées :
     - Latence des réponses LLM
     - Qualité du retrieval (relevance score)
     - Taux d'utilisation / tokens consommés
     - Satisfaction utilisateur (feedback thumbs up/down)
   - Stack : Prometheus + Grafana (ou Langfuse/LangSmith pour le LLM)
   - Dashboards et alertes configurées

4. **Tests automatisés** (~3 pages) → *C12*
   - Tests unitaires des fonctions de retrieval
   - Tests d'intégration de l'API (pytest + httpx)
   - Tests de qualité du RAG : jeu de questions/réponses attendues (eval dataset)
   - Tests de non-régression du modèle

5. **CI/CD du service IA** (~3 pages) → *C13*
   - Pipeline GitHub Actions / GitLab CI :
     ```
     lint → tests → build Docker → push registry → deploy staging → smoke tests → deploy prod
     ```
   - Déploiement automatique quand la base de documents est mise à jour (ré-indexation)
   - Rollback automatique si les métriques dégradent

### 🖥️ Démo à préparer :
- Poser une question au RAG → montrer la réponse contextualisée + les sources citées
- Utiliser l'agent pour exécuter une tâche (ex: « Analyse les ventes du mois dernier ») → montrer le raisonnement de l'agent
- Montrer le dashboard Grafana avec les métriques en temps réel
- Montrer le pipeline CI/CD qui tourne

### 💬 Ce que le jury veut entendre :
> « J'ai développé une API REST pour le service RAG, intégré un agent IA dans l'application existante, mis en place un monitoring des performances du LLM, automatisé les tests et créé un pipeline CI/CD complet. »

---

## 📌 Épreuve E4 — Développement de l'application complète
**Rapport : 15-20 pages | 20 min + DÉMO | C14-C19**

### 🎯 Angle : « Comment j'ai conçu, développé et livré l'application web de A à Z »

C'est ici que tu prends du recul et tu montres **l'application dans sa globalité** : de l'analyse du besoin à la mise en production.

### 📄 Plan du rapport (15-20 pages)

1. **Analyse du besoin** (~3 pages) → *C14*
   - Contexte entreprise et problématique métier
   - Spécifications fonctionnelles (user stories, personas)
   - Maquettes / wireframes (Figma)
   - Contraintes d'accessibilité et d'utilisabilité

2. **Conception technique** (~4 pages) → *C15*
   - Architecture applicative (schéma détaillé — voir ci-dessus)
   - Choix de la pile technique justifié :
     - Frontend : React/Vue/Next.js — pourquoi ?
     - Backend : FastAPI/Django — pourquoi ?
     - BDD : PostgreSQL + ChromaDB — pourquoi ?
     - IA : LangChain + Mistral — pourquoi ?
   - Diagrammes UML (séquence, composants, déploiement)

3. **Gestion de projet Agile** (~3 pages) → *C16*
   - Organisation en sprints (Jira / GitHub Projects)
   - Cérémonies : daily, sprint review, rétro
   - Collaboration avec l'équipe / le tuteur de stage
   - Approche MLOps : versioning des modèles, feature store

4. **Développement** (~3 pages) → *C17*
   - Composants frontend développés (dashboards, chat, formulaires)
   - API backend (endpoints, middleware, authentification)
   - Intégration de l'IA (cf. E3 — résumé ici)
   - Respect des standards : accessibilité, sécurité (OWASP), RGPD

5. **Tests** (~2 pages) → *C18*
   - Stratégie de tests (pyramide de tests)
   - Tests unitaires, d'intégration, end-to-end (Cypress/Playwright)
   - Intégration dans le CI (GitHub Actions) : tests automatiques à chaque push
   - Couverture de code

6. **Livraison continue** (~3 pages) → *C19*
   - Pipeline CI/CD complète :
     ```
     push → lint → test → build → containerize → deploy staging → tests E2E → deploy prod
     ```
   - Environnements : dev → staging → prod
   - Conteneurisation Docker + docker-compose
   - Déploiement (cloud ou serveur entreprise)

### 🖥️ Démo à préparer :
- Parcours utilisateur complet : connexion → dashboard données → analyse → question au RAG → action de l'agent
- Montrer le code source (architecture propre)
- Montrer le pipeline CI/CD qui déploie automatiquement
- Montrer les tests qui passent

### 💬 Ce que le jury veut entendre :
> « J'ai analysé le besoin, conçu l'architecture, développé l'application en méthodologie Agile, automatisé les tests et mis en place une livraison continue. L'application est en production et utilisée. »

---

## 📌 Épreuve E5 — Monitorage et résolution d'incident
**Documentation : 2-5 pages | 10 min | C20-C21**

### 🎯 Angle : « Un incident réel rencontré en prod et comment je l'ai résolu »

> [!TIP]
> Pendant ton stage, **documente chaque bug/incident sérieux** que tu rencontres. Tu en auras besoin ici. Si tu n'en as pas encore, provoque-en un en conditions de test (charge, données inattendues, etc.).

### 📄 Plan du rapport (2-5 pages)

1. **Dispositif de monitorage** (~1 page) → *C20*
   - Stack mise en place : Prometheus + Grafana + logs structurés (ou Langfuse pour le LLM)
   - Métriques surveillées, seuils d'alerte configurés
   - Journalisation (format, rétention, conformité RGPD)

2. **Description de l'incident** (~1 page) → *C21*
   - **Quoi** : ex. « Le RAG retourne des réponses hors sujet depuis 2 jours »
   - **Quand** : détecté par l'alerte Grafana le XX/XX/2026 à HHhMM
   - **Périmètre** : fonctionnalité chat RAG, tous les utilisateurs impactés

3. **Diagnostic** (~1 page) → *C21*
   - Investigation : analyse des logs, vérification du vector store, test des embeddings
   - Root cause : ex. « Un batch d'indexation a écrasé l'index avec des documents corrompus (encodage UTF-8 cassé) »

4. **Résolution** (~1 page) → *C21*
   - Fix : restauration de l'index sain + correction du script d'indexation (validation des documents avant indexation)
   - Tests de validation : requêtes de test, comparaison avant/après
   - Mesures préventives : ajout de validation en amont, alerte sur la qualité du retrieval

5. **Documentation de l'incident** (~0.5 page)
   - Fiche incident formalisée (template : sévérité, timeline, impact, résolution, actions préventives)

### 🧪 Exemples d'incidents possibles avec ton projet :

| Incident | Cause probable | C'est crédible parce que... |
|----------|---------------|---------------------------|
| RAG retourne des hallucinations | Chunks mal découpés, contexte trop large | Problème classique RAG |
| L'agent IA tourne en boucle | Boucle infinie dans le raisonnement de l'agent | Problème connu des agents LangChain |
| Latence × 5 sur l'API | Rate limit du LLM atteint, pas de cache | Réaliste en montée en charge |
| Données sensibles dans les réponses du RAG | Documents non filtrés indexés par erreur | Enjeu RGPD réel |

---

## 🗺️ Vue d'ensemble — Ton projet couvre tout

```
      TON PROJET DE STAGE
      ════════════════════

 DONNÉES MÉTIER ──────────────────────▶ E1 (2-5p)
      │                                 Collecte, nettoyage, BDD, API
      │
 CHOIX DE LA STACK IA ────────────────▶ E2 (15-20p)
      │                                 Veille, benchmark LLM/RAG/Vector
      │
 SERVICE RAG + AGENT IA ──────────────▶ E3 (15-20p)
      │                                 API, intégration, monitoring, CI/CD
      │
 APPLICATION WEB COMPLÈTE ────────────▶ E4 (15-20p)
      │                                 Archi, dev, tests, déploiement
      │
 INCIDENT EN PROD ────────────────────▶ E5 (2-5p)
                                        Monitoring, diagnostic, résolution
```

> [!IMPORTANT]
> **Attention au piège** : même si c'est le même projet, chaque rapport doit avoir un **angle différent**. Ne te répète pas.
> - E1 = les **données** (pipeline, SQL, API)
> - E2 = la **veille et le choix** (recherche, comparaison, recommandation)
> - E3 = le **service IA** (API du RAG, agent, MLOps)
> - E4 = **l'application** (architecture, dev fullstack, CI/CD applicatif)
> - E5 = un **incident** (monitoring, debug, résolution)

---

## ⚡ Actions immédiates pour ton stage

- [ ] **Dès maintenant** : mettre en place un journal de bord (incidents, décisions techniques, choix de stack)
- [ ] **Dès le début du dev** : configurer le monitoring (même basique) pour avoir des données pour E5
- [ ] **Fais des captures d'écran** de tout : dashboards, pipelines, démos, erreurs
- [ ] **Documente tes benchmarks** au fil de l'eau (E2) — ne fais pas ça à la dernière minute
- [ ] **Prépare une vidéo de backup** de tes démos (E3, E4) au cas où ça plante le jour J
