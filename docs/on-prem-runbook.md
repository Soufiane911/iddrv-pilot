# IDDRV — runbook pilote on-premise

## Préparer l’environnement

1. Copier `.env.example` vers `.env`.
2. Remplacer `POSTGRES_PASSWORD` et `SESSION_SECRET` par des valeurs propres au site.
3. Vérifier Docker/Compose et l’espace disponible pour les volumes `timescaledb_data`, `inbox`, `archive` et `quarantine`.

```bash
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
```

Le seul service exposé sur le réseau est `web` (port `WEB_PORT`, 8080 par défaut). PostgreSQL et Redis sont liés à localhost pour le diagnostic local et ne sont pas publiés sur le LAN.

## Premier accès et import

Ouvrir `http://localhost:${WEB_PORT:-8080}`. Déposer les fichiers dans `data/inbox/<site>/<source>/`. Le worker attend un fichier stable, le traite une seule fois, puis le déplace vers `archive/` ou `quarantine/`.

Créer le premier administrateur interactif (le mot de passe n’est jamais passé
sur la ligne de commande) :

```bash
DATABASE_URL='postgresql://...' python scripts/create_admin.py admin@site.local --site-id 1
```

```bash
docker compose logs -f worker api
```

Un fichier invalide reste en quarantaine avec son erreur et son historique d’import. Une nouvelle copie du même hash est sans effet métier.

## Sauvegarde / restauration

```bash
DATABASE_URL='postgresql://...' DB_CONTAINER=timescaledb BACKUP_DIR=./backups ./scripts/backup.sh
DATABASE_URL='postgresql://...' DB_CONTAINER=timescaledb BACKUP_FILE=./backups/iddrv-<stamp>.dump ./scripts/restore.sh
```

La sauvegarde comprend le dump public et un sidecar CSV des cycles TimescaleDB.
La base cible doit d’abord être initialisée par `db/setup_db.py`/Compose ; le
script remplace ensuite les données métier et recharge les cycles. Tester la
restauration dans une base isolée avant toute restauration de production.

## Redémarrage et mise à jour

```bash
docker compose restart api worker web
docker compose up -d --build
docker compose ps
```

Les migrations sont idempotentes et rejouées par le service API au démarrage. Vérifier `/health`, les logs du worker et le nombre de passeports terminés avant de remettre l’atelier en exploitation.

## Limites du pilote

- La 3D est optionnelle et désactivée par défaut (`VITE_ENABLE_3D=false`).
- L’investigateur actif est déterministe/local ; aucun appel OpenAI n’est requis.
- L’adaptateur Arburg/Selogica/Gestica est prêt à qualifier, mais n’est pas déclaré validé terrain sans export réel.
