# Épreuve E4 — Réalisation de l’application complète

**Compétences :** C14 à C19 — **Durée :** 20 minutes  
**Message central :** IDDRV relie ingestion, supervision, investigation et décision humaine dans une application on-premise complète.

## Déroulé conseillé

1. **Besoin et utilisateurs — 2 min 30**
   - Données industrielles fragmentées ; opérateur, analyste, superviseur et administrateur.
   - Passer d’un signal atelier à une investigation fondée sur des preuves.

2. **Architecture — 3 min**
   - React/Vite/TypeScript, FastAPI/Pydantic, PostgreSQL/TimescaleDB, Redis et Docker Compose.
   - Monolithe modulaire pour limiter la complexité du pilote.

3. **Organisation — 2 min**
   - Gates G0 à G6, périmètres séparés, contrats DB/API figés, handoffs, revues et tests.
   - Ne pas inventer de cérémonies Scrum non réalisées.

4. **Fonctionnalités — 3 min**
   - Cookie HttpOnly, rôles par site, atelier 2D et 3D optionnelle, replay temporel.
   - Incidents, hypothèses, preuves, feedback, imports et santé des services.

5. **Qualité et sécurité — 2 min 30**
   - Tests Python, API, E2E, frontend et navigateur.
   - Isolation multi-site, permissions, secrets hors dépôt, DB non exposée au LAN.
   - Aucune commande directe envoyée aux presses.

6. **Livraison — 2 min**
   - Images Docker, web seul exposé, sauvegarde et restauration.
   - Dire « prêt pour pilote », pas « validé terrain ».

7. **Démonstration — 5 min**
   - Connexion → site → atelier → machine/replay → incident → investigation → preuve/feedback → imports ou santé.

## Preuves

- `docs/project/original-request.md`
- `docs/orchestrated-implementation-plan.md`
- `docs/api-v1-contract.md`
- `docs/on-prem-runbook.md`
- `frontend/src/`, `backend/app/`, `docker-compose.yml`

## Questions probables

- Pourquoi un monolithe modulaire ?
- Comment garantissez-vous l’isolation multi-site ?
- Pourquoi la 3D est-elle optionnelle ?
- Comment gérez-vous les rôles ?
- Que signifie « prêt pour pilote » ?
