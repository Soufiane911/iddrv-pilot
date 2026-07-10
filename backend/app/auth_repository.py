"""Persistence helpers for users and revocable local sessions."""

from __future__ import annotations

import json
import os
from datetime import datetime

import psycopg2

from .db import get_connection
from .security import Identity, hash_password, token_hash, verify_password


def _identity(row, site_rows=()):
    return Identity(
        user_id=str(row[0]),
        email=str(row[1]),
        display_name=str(row[2]),
        role=str(row[3]),
        site_ids=tuple(int(item[0]) for item in site_rows),
    )


def _dev_users() -> list[dict]:
    """Optional env-only accounts for a fresh local pilot.

    The value must contain password hashes (never plaintext passwords), e.g.
    ``[{"email":"admin@example.test","password_hash":"$argon2id$...",...
    }]``.  This avoids shipping credentials while keeping a clean DB usable.
    """

    raw = os.getenv("IDDVR_DEV_USERS_JSON", "[]")
    try:
        values = json.loads(raw)
        return values if isinstance(values, list) else []
    except json.JSONDecodeError:
        return []


def authenticate(email: str, password: str) -> Identity | None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT u.id,u.email,u.display_name,r.role
                       FROM users u JOIN user_site_roles r ON r.user_id=u.id
                       WHERE lower(u.email)=lower(%s) AND u.is_active=true
                       ORDER BY CASE r.role WHEN 'admin' THEN 4 WHEN 'supervisor' THEN 3 WHEN 'analyst' THEN 2 ELSE 1 END DESC
                       LIMIT 1""",
                    (email,),
                )
                row = cur.fetchone()
                if row is not None:
                    cur.execute("SELECT site_id FROM user_site_roles WHERE user_id=%s", (row[0],))
                    sites = cur.fetchall()
                    cur.execute("SELECT password_hash FROM users WHERE id=%s", (row[0],))
                    password_row = cur.fetchone()
                    if password_row and verify_password(password, password_row[0]):
                        return _identity(row, sites)
    except psycopg2.Error:
        # A fresh checkout can be used for read-only demo exploration before
        # migration 004 is applied.  Do not turn this into a bypass for writes.
        pass

    for value in _dev_users():
        if str(value.get("email", "")).lower() == email.lower() and verify_password(password, str(value.get("password_hash", ""))):
            role = str(value.get("role", "viewer"))
            if role not in {"viewer", "analyst", "supervisor", "admin"}:
                continue
            return Identity(
                user_id=str(value.get("id", email)),
                email=email,
                display_name=str(value.get("display_name", email)),
                role=role,
                site_ids=tuple(int(site) for site in value.get("site_ids", [])),
            )
    return None


def create_user(email: str, password: str, display_name: str, role: str, site_ids: list[int]):
    """Create a local account and assign its site scope atomically."""
    if role not in {"viewer", "analyst", "supervisor", "admin"}:
        raise ValueError("invalid_role")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users(email,password_hash,display_name) VALUES (%s,%s,%s) RETURNING id,email,display_name",
                (email, hash_password(password), display_name),
            )
            row = cur.fetchone()
            if not site_ids:
                cur.execute("SELECT id FROM sites ORDER BY id LIMIT 1")
                first = cur.fetchone()
                site_ids = [int(first[0])] if first else []
            for site_id in sorted(set(site_ids)):
                cur.execute("INSERT INTO user_site_roles(user_id,site_id,role) VALUES (%s,%s,%s)", (row[0], site_id, role))
            conn.commit()
    return Identity(str(row[0]), str(row[1]), str(row[2]), role, tuple(sorted(set(site_ids))))


def save_session(identity: Identity, token: str, expires_at: datetime) -> str | None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions(user_id,token_hash,expires_at,last_seen_at) VALUES (%s,%s,%s,NOW()) RETURNING id",
                    (identity.user_id, token_hash(token), expires_at),
                )
                row = cur.fetchone()
                conn.commit()
                return str(row[0]) if row else None
    except (psycopg2.Error, ValueError):
        return None


def replace_session_token(session_id: str, token: str, expires_at: datetime) -> None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE sessions SET token_hash=%s,expires_at=%s,last_seen_at=NOW() WHERE id=%s", (token_hash(token), expires_at, session_id))
                conn.commit()
    except psycopg2.Error:
        return


def revoke_session(token: str) -> None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE sessions SET revoked_at=NOW() WHERE token_hash=%s", (token_hash(token),))
                conn.commit()
    except psycopg2.Error:
        return


def session_is_active(identity: Identity, token: str) -> bool:
    if identity.anonymous or not identity.session_id:
        return True
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM sessions WHERE id=%s AND token_hash=%s AND revoked_at IS NULL AND expires_at>NOW()",
                    (identity.session_id, token_hash(token)),
                )
                return cur.fetchone() is not None
    except psycopg2.Error:
        # Signed token remains valid when the optional control-plane table is
        # temporarily unavailable; revocation is best effort in a local demo.
        return True
