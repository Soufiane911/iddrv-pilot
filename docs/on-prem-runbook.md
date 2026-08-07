# IDDRV — runbook pilote on-premise

## Préparer l’environnement

1. Copier `.env.example` vers `.env`.
2. Générer des valeurs propres au site pour `POSTGRES_PASSWORD` et `SESSION_SECRET` (32 caractères aléatoires au minimum pour ce dernier).
3. Renseigner `DATABASE_URL` avec l’hôte `localhost` et `DOCKER_DATABASE_URL` avec l’hôte `timescaledb`. Les deux URL doivent reprendre le même mot de passe, encodé pour une URL (`@`, `:`, `/`, `#`, `%`, etc.).
4. Vérifier Docker/Compose et l’espace disponible pour les volumes `timescaledb_data`, `inbox`, `archive` et `quarantine`.

```bash
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
```

Par défaut, `web`, PostgreSQL et Redis sont liés à `127.0.0.1` et ne sont pas publiés sur le LAN. Pour un accès LAN, placer un reverse proxy HTTPS devant `127.0.0.1:${WEB_PORT:-8080}`, définir `SESSION_COOKIE_SECURE=true` et ne pas exposer directement le port HTTP.

## Premier accès et import

Ouvrir `http://localhost:${WEB_PORT:-8080}`. Déposer les fichiers dans `data/inbox/<site>/<source>/`. Le worker attend un fichier stable, le traite une seule fois, puis le déplace vers `archive/` ou `quarantine/`.

Créer le premier administrateur interactif (le mot de passe n’est jamais passé
sur la ligne de commande) :

```bash
# DATABASE_URL doit déjà être exportée depuis le fichier local protégé.
python scripts/create_admin.py admin@site.local --site-id 1
```

```bash
docker compose logs -f worker api
```

Un fichier invalide reste en quarantaine avec son erreur et son historique d’import. Une nouvelle copie du même hash est sans effet métier.

## Sauvegarde / restauration

```bash
# DATABASE_URL est exportée depuis un fichier local protégé, pas saisie dans l’historique shell.
DB_CONTAINER=timescaledb BACKUP_DIR=./backups ./scripts/backup.sh

# La cible doit être une autre base, fraîche et déjà initialisée sur le même serveur.
DB_CONTAINER=timescaledb \
RESTORE_TARGET_DATABASE=iddrv_restore_20260713 \
RESTORE_TARGET_ISOLATED=true \
BACKUP_FILE=./backups/iddrv-<stamp>.dump \
DATABASE_URL="$RESTORE_DATABASE_URL" \
./scripts/restore.sh
```

La sauvegarde comprend le dump public et un sidecar CSV des cycles TimescaleDB.
Les outils PostgreSQL reçoivent les secrets via un fichier temporaire protégé, jamais
par leurs arguments. La restauration refuse une cible distante, une base dont le nom
ne correspond pas à `RESTORE_TARGET_DATABASE`, un autre serveur que le conteneur
Compose, des sessions actives ou des données applicatives préexistantes. Elle ne
suspend pas l’application active puisqu’elle travaille obligatoirement dans une base
isolée. Valider cette base, sauvegarder la configuration courante, puis basculer
`DATABASE_URL`/`DOCKER_DATABASE_URL` et redémarrer API/worker. Ne jamais écraser
directement la base de production.

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
