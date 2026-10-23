"""Postgres connection and a minimal migration runner.

Migrations are plain SQL files in ingest/migrations/, applied in filename order
and recorded in schema_migrations. Each file runs in its own transaction.
"""
import csv
import os
from pathlib import Path

import psycopg

from .filter import AIRLINES_CSV

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def database_url():
    """DATABASE_URL, or one composed from the POSTGRES_* variables used by Compose."""
    if url := os.environ.get("DATABASE_URL"):
        return url
    user = os.environ.get("POSTGRES_USER", "at_tracker")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "at_tracker")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def connect(url=None):
    """Autocommit connection: writes are grouped explicitly with conn.transaction()."""
    return psycopg.connect(url or database_url(), autocommit=True)


def migrate(conn, migrations_dir=MIGRATIONS):
    """Apply pending migrations. Returns the names applied."""
    with conn.transaction():
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                     "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name in done:
            continue
        with conn.transaction():
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        applied.append(path.name)
    return applied


def seed_airlines(conn, path=AIRLINES_CSV):
    """Sync the airlines table with the allowlist CSV (insert, update, delete)."""
    with open(path, newline="") as f:
        rows = [(r["icao"], r["iata"] or None, r["name"], r["kind"]) for r in csv.DictReader(f)]
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO airlines (icao, iata, name, kind) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (icao) DO UPDATE SET iata = EXCLUDED.iata, name = EXCLUDED.name, kind = EXCLUDED.kind",
            rows)
        cur.execute("DELETE FROM airlines WHERE NOT (icao = ANY(%s))", ([r[0] for r in rows],))
    return len(rows)
