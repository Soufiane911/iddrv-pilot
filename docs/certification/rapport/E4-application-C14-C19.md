# Rapport E4 — Réalisation de l'application complète

**Compétences :** C14 à C19 — **Pages cible :** 15–20 — **Statut :** brouillon rédigé (à illustrer avec les captures de parcours)

---

## 1. Besoin et utilisateurs (C14)

Dans une usine de plasturgie par injection, les données de production existent à
**deux grains incompatibles** :

- **macro** : l'ERP décrit les OF, les équipes et le TRS (heures, quantités,
  rebuts par équipe) ;
- **micro** : les presses (Arburg, Engel) produisent un signal **par cycle**
  (temps, pressions, températures, forces, énergie).

Sans rapprochement, un incident qualité ne peut pas être relié à la machine, à
l'OF et aux réglages qui l'ont produit. Le besoin d'IDDRV est de **relier le
signal atelier à une investigation fondée sur des preuves**.

**Utilisateurs cibles** :

| Rôle | Besoin |
|---|---|
| Opérateur | Voir l'état de l'atelier, les alertes et les priorités d'inspection |
| Analyste | Investiguer un incident, consulter hypothèses et preuves, donner un feedback |
| Superviseur | Piloter la qualité, suivre les dérives et les actions |
| Administrateur | Gérer les accès, surveiller la santé du système, les imports |

## 2. Architecture technique (C15)

| Couche | Technologie |
|---|---|
| Frontend | React + Vite + TypeScript (2D complète ; 3D Three.js **optionnelle**, désactivée par défaut `VITE_ENABLE_3D=false`) |
| Backend | FastAPI + Pydantic (contrats validés) |
| Stockage | PostgreSQL (référentiel applicatif) + TimescaleDB (hypertable `machine_cycles`) |
| Cache/état | Redis |
| Ingestion | Worker watched-folder (`inbox → processing → archive/quarantine`) |
| Packaging | Docker Compose on-prem : `timescaledb`, `api`, `worker`, `redis`, `web` |

**Choix du monolithe modulaire** : pour un pilote, un seul backend FastAPI avec
des modules clairement séparés (API, ingestion, diagnostic, sécurité) limite la
complexité opérationnelle (un seul conteneur à surveiller, migrations uniques)
tout en conservant des frontières de code nettes. Une découpe en microservices
serait prématurée pour 5 conteneurs.

**Exposition réseau** : seuls `web` (UI) et les services internes sont dans le
Compose ; **DB et Redis restent liés à 127.0.0.1** — la DB n'est pas exposée au
LAN. L'accès LAN se fait via un reverse proxy HTTPS devant le web.

## 3. Organisation du projet (C16)

Le projet a été conduit par **gates successives** (G0 → G6), chacune avec un
périmètre, une revue et des tests de sortie :

| Gate | Contenu | Preuve de sortie |
|---|---|---|
| G0 | Préparation Git, rôles d'agents, règles de sécurité | config Compose valide, smoke read-only |
| G1 | Schéma + dataset réaliste intégral en base | **60 OF / 38 313 cycles / 408 checks qualité / 12 maintenances / 10 notes** ; 80 tests |
| G2 | Incident S001 vertical + API v1 | investigation 200 avec preuves persistées |
| G3 | Interface 2D, replay, investigation | parcours navigateur Playwright validé |
| G4 | Auth, multi-site, investigateur local | 404 cross-site, 403 viewer, Top-2 recall 100 % |
| G5 | Worker d'ingestion automatisé | 16 checks ingestion, idempotence SHA-256 |
| G6 | Packaging on-prem, 3D optionnelle, backup/restore | **50 E2E passés**, 38 313 cycles restaurés, Compose valide |

L'organisation réelle reposait sur : contrats DB/API figés en amont, périmètres
d'agents séparés (data, backend, frontend, diagnostic), handoffs documentés et
revues à chaque gate. **Aucune cérémonie Scrum n'a été inventée** : le processus
effectif (gates, revues, tests) est celui raconté ici.

## 4. Fonctionnalités et parcours (C17)

**Sécurité et accès** :

- mots de passe hachés **Argon2id**, cookie de session **HttpOnly/SameSite=Strict**,
  identité signée, **RBAC** viewer/analyst/supervisor/admin ;
- **isolation par site** : un client d'un site reçoit 404 sur les données d'un
  autre site.

**Fonctionnalités principales** :

- **Atelier 2D** (SVG) : état des machines par couleur, sélection clavier,
  replay temporel d'une machine ;
- **Atelier 3D optionnelle** (Three.js) : vue d'ensemble, désactivée par défaut,
  fallback 2D complet ;
- **Incidents et investigation** : hypothèses, preuves (avec citations),
  contradictions, prochaine vérification, **feedback humain** ;
- **Dérive process (HDT)** : panneau score/seuil/signaux/version avec
  abstention tant que les cycles bruts ne sont pas raccordés ;
- **Imports** : statuts des fichiers (inbox, processing, archive, quarantaine),
  passports d'import ;
- **Santé** : `/health`, `/metrics` protégé, statuts des services.

**Parcours de démonstration** : connexion → liste des sites → atelier →
sélection machine/replay → incident → investigation (hypothèses + preuves) →
feedback → imports ou santé.

## 5. Qualité, sécurité, tests (C18)

**Chaîne de tests** (exécutée en local, équivalente CI) :

| Niveau | Contenu | Résultat de référence |
|---|---|---|
| Python unitaire | Pipeline ingestion, diagnostic, API, ML | 75–80 passés (G1 : 80) |
| E2E isolé | Harness `tests/e2e/run_tests.py` sur base fraîche | **50 passed, 0 failed** (G6) |
| Frontend | Vitest (composants, parcours) | 62 tests (post-fix) |
| Navigateur | Playwright (site → atelier → replay → incident → investigation) | passé (G3) |
| Lint/build | ESLint + production build | passés |

**Sécurité** :

- secrets hors dépôt (`.env` non versionné, `.env.example` documenté) ;
- **DB non exposée au LAN**, Redis local ;
- aucune commande directe envoyée aux presses (lecture seule de la supervision) ;
- isolation multi-site vérifiée par tests (404/403) ;
- **aucun appel OpenAI** dans le code runtime (intégration différée, scan vérifié).

## 6. Livraison on-prem (C19)

- **Images Docker** : services `timescaledb`, `api`, `worker`, `redis`, `web` ;
  `docker compose config --quiet` valide ;
- **web seul exposé au LAN** (reverse proxy HTTPS recommandé,
  `SESSION_COOKIE_SECURE=true`) ;
- **Sauvegarde/restauration** : `scripts/backup.sh` (dump public + sidecar CSV
  des cycles TimescaleDB), `scripts/restore.sh` (refuse cible distante, base
  non isolée, sessions actives, données préexistantes) — smoke testé :
  **38 313 cycles restaurés** ;
- **Migrations idempotentes** rejouées au démarrage de l'API ;
- **Runbook** : `docs/on-prem-runbook.md` (démarrage, premier admin, import,
  backup/restore, redémarrage).

**Limites assumées** :

- la construction d'images Docker n'a pas été finalisée sur cette machine
  (téléchargements de métadonnées registry bloqués) — la recette Compose est
  prête à construire dans un environnement connecté ;
- pas de registry cloud ni de pipeline CD : livraison par images/Compose
  versionnés ;
- la 3D est optionnelle ; l'adaptateur Arburg/Selogica/Gestica est prêt à
  qualifier mais pas déclaré validé terrain.

## 7. Conclusion

IDDRV relie l'ingestion, la supervision, l'investigation fondée sur preuves et
la décision humaine dans une **application on-premise complète**, organisée par
gates, testée à tous les niveaux et livrée avec un runbook d'exploitation.
L'ensemble est **« prêt pour pilote »** : démontré en environnement de test sur
un jeu synthétique réaliste ; la qualification terrain (exports réels, accès
LAN sécurisé, validation process) reste la prochaine étape.

## 8. Preuves

- `docs/project/original-request.md`, `docs/product/product-brief.md` — besoin (C14)
- `docs/orchestrated-implementation-plan.md`, `docs/implementation-status.md` — gates G0–G6 (C16)
- `docs/api-v1-contract.md` — contrats API (C15)
- `docs/on-prem-runbook.md`, `docker-compose.yml`, `scripts/backup.sh`, `scripts/restore.sh` — livraison (C19)
- `docs/product/frontend-evidence.md`, `docs/product/visual-system.md` — UI (C17)
- `frontend/src/`, `backend/app/`, `tests/`, `ingest/`, `ml/` — code
- `README.md` — vue d'ensemble et démarrage
