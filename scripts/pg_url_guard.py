#!/usr/bin/env python3
"""Prepare a PostgreSQL URL for CLI use without exposing credentials in argv."""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlsplit, urlunsplit

ROUTING_KEYS = {"host", "hostaddr", "dbname", "service", "servicefile", "passfile"}
SENSITIVE_KEYS = {"password", "passwd", "pwd", "token", "secret"}


def parse_database_url(value: str):
    parsed = urlsplit(value)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL doit utiliser le schéma postgresql://")
    if not parsed.hostname or not parsed.username or not parsed.path.lstrip("/"):
        raise ValueError("DATABASE_URL doit préciser utilisateur, hôte et base")
    query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    forbidden = query_keys & (ROUTING_KEYS | SENSITIVE_KEYS)
    if forbidden:
        raise ValueError(f"Paramètre DATABASE_URL interdit: {sorted(forbidden)[0]}")
    return parsed


def pgpass_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:")


def passwordless_url(parsed) -> str:
    hostname = parsed.hostname or ""
    rendered_host = f"[{hostname}]" if ":" in hostname else hostname
    if parsed.port:
        rendered_host = f"{rendered_host}:{parsed.port}"
    username = quote(unquote(parsed.username or ""), safe="")
    return urlunsplit(parsed._replace(netloc=f"{username}@{rendered_host}"))


def write_passfile(parsed, path: Path) -> None:
    password = unquote(parsed.password or "")
    line = ":".join(
        [
            pgpass_escape(parsed.hostname or ""),
            str(parsed.port or 5432),
            "*",
            pgpass_escape(unquote(parsed.username or "")),
            pgpass_escape(password),
        ]
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"{line}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--passfile", type=Path, required=True)
    parser.add_argument("--require-local", action="store_true")
    args = parser.parse_args()
    try:
        parsed = parse_database_url(os.environ.get("DATABASE_URL", ""))
        if args.require_local and parsed.hostname not in {"localhost", "127.0.0.1", "::1", "timescaledb"}:
            raise ValueError("La restauration on-premise refuse une cible PostgreSQL distante")
        write_passfile(parsed, args.passfile)
        print(passwordless_url(parsed))
        return 0
    except (ValueError, OSError) as error:
        print(f"Database URL refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
