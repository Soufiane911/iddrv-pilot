#!/usr/bin/env python3
"""
IDDRV — Script de setup standalone de la base de données
=========================================================

Connecte à PostgreSQL, exécute init.sql puis seed_data.sql,
vérifie l'hypertable machine_cycles et affiche un rapport de validation.

Usage :
    python db/setup_db.py
    DATABASE_URL=postgresql://... python db/setup_db.py
"""

import os
import sys
import time
import argparse
import re
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("[ERREUR] psycopg2 n'est pas installé. Exécutez : pip install psycopg2-binary")
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iddrv_user:iddrv_secret_2024@localhost:5432/iddrv"
)

# Chemins relatifs au répertoire du script
SCRIPT_DIR = Path(__file__).parent
INIT_SQL   = SCRIPT_DIR / "init.sql"
SEED_SQL   = SCRIPT_DIR / "seed_data.sql"
CURRENT_SCHEMA_VERSION = (1, 0, 0)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _banner(title: str):
    width = 62
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def _ok(msg: str):
    print(f"  ✅  {msg}")


def _warn(msg: str):
    print(f"  ⚠️   {msg}")


def _err(msg: str):
    print(f"  ❌  {msg}", file=sys.stderr)


def wait_for_postgres(url: str, retries: int = 10, delay: float = 2.0) -> bool:
    """Attend que PostgreSQL soit prêt avant de continuer."""
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(url, connect_timeout=5)
            conn.close()
            return True
        except psycopg2.OperationalError as exc:
            print(f"  [ATTENTE] PostgreSQL non disponible (tentative {attempt}/{retries}) : {exc}")
            time.sleep(delay)
    return False


def execute_sql_file(cursor, sql_path: Path):
    """Exécute un fichier SQL (supporte les blocs DO $$ ... $$ et multi-statements)."""
    if not sql_path.exists():
        raise FileNotFoundError(f"Fichier SQL introuvable : {sql_path}")

    sql_content = sql_path.read_text(encoding="utf-8")
    print(f"  → Exécution de {sql_path.name} ({len(sql_content)} octets) …")

    # psycopg2 n'exécute pas les fichiers multi-statements directement ;
    # on utilise execute() qui accepte le SQL brut via mogrify via executescript-like.
    # Pour la compatibilité, on utilise psycopg2 avec autocommit=True sur DDL.
    cursor.execute(sql_content)


def _version_tuple(value: str) -> tuple[int, ...]:
    """Convertit v1.2.3 ou 1.2.3 vers un tuple comparable."""
    parts = re.findall(r"\d+", value or "")
    return tuple(int(part) for part in parts) if parts else (0,)


def assert_schema_version_compatible(cursor):
    """Refuse d'appliquer ce setup sur un schéma plus récent."""
    cursor.execute("SELECT to_regclass('public.schema_version') AS relation")
    if not cursor.fetchone()["relation"]:
        return

    cursor.execute("SELECT version FROM schema_version LIMIT 1")
    row = cursor.fetchone()
    if row and _version_tuple(row["version"]) > CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Schema version {row['version']} is newer than supported version "
            f"{'.'.join(map(str, CURRENT_SCHEMA_VERSION))}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Vérifications post-setup
# ──────────────────────────────────────────────────────────────────────────────

def check_extensions(cursor) -> dict:
    """Vérifie les extensions PostgreSQL activées."""
    cursor.execute("""
        SELECT extname, extversion
        FROM pg_extension
        WHERE extname IN ('timescaledb', 'uuid-ossp', 'pg_trgm')
        ORDER BY extname
    """)
    return {row["extname"]: row["extversion"] for row in cursor.fetchall()}


def check_tables(cursor) -> list:
    """Retourne la liste des tables du schéma public."""
    cursor.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    return [row["tablename"] for row in cursor.fetchall()]


def check_hypertable(cursor) -> dict | None:
    """Vérifie que machine_cycles est une hypertable TimescaleDB."""
    cursor.execute("""
        SELECT hypertable_name, num_dimensions, num_chunks
        FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'machine_cycles'
    """)
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


def check_continuous_aggregates(cursor) -> list:
    """Retourne les vues agrégées continues (materialized views TimescaleDB)."""
    cursor.execute("""
        SELECT view_name, materialization_hypertable_name
        FROM timescaledb_information.continuous_aggregates
        ORDER BY view_name
    """)
    return [dict(row) for row in cursor.fetchall()]


def check_seed_data(cursor) -> dict:
    """Vérifie que les données de référence ont bien été insérées."""
    cursor.execute("SELECT COUNT(*) AS cnt FROM machines")
    machines_count = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) AS cnt FROM machine_aliases")
    aliases_count = cursor.fetchone()["cnt"]

    return {"machines": machines_count, "aliases": aliases_count}


def check_indexes(cursor) -> list:
    """Liste les index créés sur les tables principales."""
    cursor.execute("""
        SELECT indexname, tablename
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename IN ('machine_cycles', 'machines', 'production_orders', 'import_passports')
        ORDER BY tablename, indexname
    """)
    return [dict(row) for row in cursor.fetchall()]


# ──────────────────────────────────────────────────────────────────────────────
# Rapport de validation
# ──────────────────────────────────────────────────────────────────────────────

def print_validation_report(conn):
    """Affiche le rapport de validation complet après setup."""
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    _banner("RAPPORT DE VALIDATION IDDRV")

    # 1. Extensions
    print("\n  📦  Extensions PostgreSQL :")
    exts = check_extensions(cursor)
    for name, version in exts.items():
        _ok(f"{name} v{version}")
    for required in ["timescaledb", "uuid-ossp", "pg_trgm"]:
        if required not in exts:
            _warn(f"Extension manquante : {required}")

    # 2. Tables
    print("\n  🗂️   Tables créées :")
    tables = check_tables(cursor)
    expected_tables = [
        "data_quality_issues", "evidence_vault", "import_passports",
        "machine_aliases", "machine_cycles", "machines",
        "production_orders", "shifts"
    ]
    for t in tables:
        marker = "✅" if t in expected_tables else "ℹ️"
        print(f"       {marker}  {t}")
    for t in expected_tables:
        if t not in tables:
            _err(f"Table manquante : {t}")

    # 3. Hypertable
    print("\n  ⏱️   Hypertable TimescaleDB :")
    ht = check_hypertable(cursor)
    if ht:
        _ok(f"machine_cycles est une hypertable ({ht['num_dimensions']} dimension(s), {ht['num_chunks']} chunk(s))")
    else:
        _err("machine_cycles n'est PAS une hypertable — vérifiez TimescaleDB")

    # 4. Agrégats continus
    print("\n  📊  Vues agrégées continues :")
    caggs = check_continuous_aggregates(cursor)
    if caggs:
        for cagg in caggs:
            _ok(f"{cagg['view_name']} → {cagg['materialization_hypertable_name']}")
    else:
        _warn("Aucune vue agrégée continue détectée")

    # 5. Index
    print("\n  🔍  Index :")
    indexes = check_indexes(cursor)
    for idx in indexes:
        print(f"       ℹ️   [{idx['tablename']}] {idx['indexname']}")

    # 6. Données de seed
    print("\n  🌱  Données de référence :")
    seed = check_seed_data(cursor)
    if seed["machines"] > 0:
        _ok(f"{seed['machines']} machines insérées")
    else:
        _warn("Aucune machine en base — seed_data.sql n'a peut-être pas été exécuté")
    if seed["aliases"] > 0:
        _ok(f"{seed['aliases']} alias machines insérés")

    # Score global
    issues = (
        len([r for r in ["timescaledb", "uuid-ossp"] if r not in exts])
        + len([t for t in expected_tables if t not in tables])
        + (0 if ht else 1)
        + (0 if seed["machines"] > 0 else 1)
    )

    print()
    if issues == 0:
        print("  🎉  Base de données IDDRV prête ! Tous les contrôles sont OK.")
    else:
        print(f"  ⚠️   Setup terminé avec {issues} avertissement(s). Vérifiez les erreurs ci-dessus.")

    cursor.close()
    return issues == 0


# ──────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ──────────────────────────────────────────────────────────────────────────────

def main():
    global DB_URL

    parser = argparse.ArgumentParser(description="Initialise la base IDDRV PostgreSQL/TimescaleDB")
    parser.add_argument("--db-url", default=DB_URL, help="URL PostgreSQL cible")
    parser.add_argument("--seed", action="store_true", help="Conservé pour compatibilité : le seed est exécuté par défaut")
    parser.add_argument("--simulate-no-timescale", action="store_true", help="Option de test : simule TimescaleDB indisponible")
    args = parser.parse_args()

    DB_URL = args.db_url

    _banner("IDDRV — Setup de la base de données")
    print(f"\n  🔗  URL : {DB_URL.split('@')[-1]}")  # masque le mot de passe

    if args.simulate_no_timescale:
        _err("timescaledb indisponible (simulation demandée)")
        sys.exit(2)

    # 1. Attendre PostgreSQL (connexion sur 'postgres' pour s'assurer de l'existence du DB de secours)
    import urllib.parse
    parsed = urllib.parse.urlparse(DB_URL)
    target_db = parsed.path.lstrip("/")
    
    # URL de connexion par défaut vers postgres
    default_url = urllib.parse.urlunparse(parsed._replace(path="/postgres"))

    print("\n  ⏳  Attente de PostgreSQL …")
    if not wait_for_postgres(default_url):
        _err("Impossible de se connecter à PostgreSQL après plusieurs tentatives.")
        _err("Vérifiez que le conteneur Docker est démarré : docker compose up -d timescaledb")
        sys.exit(1)
    _ok("PostgreSQL disponible")

    # Créer la base de données cible si elle n'existe pas
    try:
        conn = psycopg2.connect(DB_URL)
        conn.close()
    except psycopg2.OperationalError as e:
        if "does not exist" in str(e) or "n'existe pas" in str(e):
            print(f"  Empty database '{target_db}' does not exist. Creating database '{target_db}'...")
            try:
                conn_default = psycopg2.connect(default_url)
                conn_default.autocommit = True
                with conn_default.cursor() as cur:
                    cur.execute(f"CREATE DATABASE {target_db};")
                conn_default.close()
                _ok(f"Database '{target_db}' created successfully.")
            except Exception as create_err:
                _err(f"Failed to create database '{target_db}': {create_err}")
                sys.exit(1)
        else:
            _err(f"Connection error: {e}")
            sys.exit(1)

    # 2. Connexion avec autocommit pour les DDL
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        assert_schema_version_compatible(cursor)
        # 3. Exécuter init.sql
        print("\n  📄  Initialisation du schéma (init.sql) …")
        execute_sql_file(cursor, INIT_SQL)
        _ok("init.sql exécuté avec succès")

        # 3.5 Exécuter les migrations
        for migration_sql in sorted((SCRIPT_DIR / "migrations").glob("*.sql")):
            print(f"\n  ⚙️   Exécution de la migration {migration_sql.name} …")
            execute_sql_file(cursor, migration_sql)
            _ok(f"Migration {migration_sql.name} exécutée avec succès")

        # 4. Exécuter seed_data.sql
        print("\n  🌱  Insertion des données de référence (seed_data.sql) …")
        execute_sql_file(cursor, SEED_SQL)
        _ok("seed_data.sql exécuté avec succès")

    except FileNotFoundError as exc:
        _err(str(exc))
        sys.exit(1)
    except RuntimeError as exc:
        _err(str(exc))
        sys.exit(1)
    except psycopg2.Error as exc:
        # Si les tables existent déjà, ce n'est pas critique (IF NOT EXISTS gère ça)
        # mais on affiche l'erreur pour information
        print(f"\n  [INFO] Message PostgreSQL : {exc}")
        print("  (Normal si la base était déjà initialisée — continuons…)")
    finally:
        cursor.close()

    # 5. Rapport de validation
    conn2 = psycopg2.connect(DB_URL)
    success = print_validation_report(conn2)
    conn2.close()
    conn.close()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
