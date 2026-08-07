#!/usr/bin/env python3
"""Create or update the first local administrator without storing a plaintext password."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).parents[1]))
from backend.app.security import hash_password


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--display-name", default="IDDVR administrator")
    parser.add_argument("--site-id", type=int, action="append", default=None)
    args = parser.parse_args()
    site_ids = args.site_id or [1]
    password = getpass.getpass("Mot de passe admin (non affiché) : ")
    if not password:
        raise SystemExit("Le mot de passe ne peut pas être vide")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL doit être défini")
    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO users(email,password_hash,display_name)
               VALUES (%s,%s,%s)
               ON CONFLICT (lower(email)) DO UPDATE SET password_hash=EXCLUDED.password_hash,
                 display_name=EXCLUDED.display_name, is_active=true
               RETURNING id""",
            (args.email, hash_password(password), args.display_name),
        )
        user_id = cur.fetchone()[0]
        # A password reset invalidates every previously issued session.
        cur.execute("DELETE FROM sessions WHERE user_id=%s", (user_id,))
        for site_id in sorted(set(site_ids)):
            cur.execute(
                """INSERT INTO user_site_roles(user_id,site_id,role) VALUES (%s,%s,'admin')
                   ON CONFLICT (user_id,site_id) DO UPDATE SET role='admin'""",
                (user_id, site_id),
            )
    print(f"Administrateur créé/mis à jour : {args.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
