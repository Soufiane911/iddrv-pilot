#!/usr/bin/env python3
"""Seed only the isolated synthetic ``iddrv_test`` database used by E2E."""
from __future__ import annotations

import argparse
import os
from urllib.parse import urlparse

import psycopg2

from backend.app.security import hash_password


def guarded_database(url: str) -> str:
    parsed = urlparse(url)
    database = parsed.path.lstrip('/')
    if database != 'iddrv_test' or os.getenv('REFONTE_TEST_SEED') != 'true':
        raise RuntimeError('Refus: le seed exige REFONTE_TEST_SEED=true et la base iddrv_test.')
    if (parsed.hostname or '').lower() in {'iddrv-pilot', 'pilot', 'production'}:
        raise RuntimeError('Refus: cible pilote/production.')
    return database


def seed(url: str) -> None:
    guarded_database(url)
    supervisor_password = os.getenv('REFONTE_TEST_SUPERVISOR_PASSWORD')
    viewer_password = os.getenv('REFONTE_TEST_VIEWER_PASSWORD')
    if not supervisor_password or not viewer_password:
        raise RuntimeError('Les deux mots de passe synthétiques sont requis via l’environnement.')
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO sites(name,timezone) VALUES ('Recette synthétique A','Europe/Paris'),('Recette synthétique B','Europe/Paris') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO users(email,password_hash,display_name) VALUES (%s,%s,%s),(%s,%s,%s) ON CONFLICT DO NOTHING",
                    ('supervisor.refonte@example.test', hash_password(supervisor_password), 'Superviseur recette', 'viewer.refonte@example.test', hash_password(viewer_password), 'Lecteur recette'))
        cur.execute("INSERT INTO user_site_roles(user_id,site_id,role) SELECT u.id,s.id,'supervisor' FROM users u CROSS JOIN LATERAL (SELECT id FROM sites ORDER BY id LIMIT 1) s WHERE u.email='supervisor.refonte@example.test' ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO user_site_roles(user_id,site_id,role) SELECT u.id,s.id,'viewer' FROM users u CROSS JOIN LATERAL (SELECT id FROM sites ORDER BY id OFFSET 1 LIMIT 1) s WHERE u.email='viewer.refonte@example.test' ON CONFLICT DO NOTHING")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-url', default=os.getenv('OWNER_DATABASE_URL') or os.getenv('DATABASE_URL'))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit('DATABASE_URL requis')
    seed(args.database_url)
