import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from at_ingest import db

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
TEST_DB = "at_tracker_test"


def _url_for(dbname):
    base = os.environ.get("TEST_DATABASE_URL") or db.database_url()
    return base.rsplit("/", 1)[0] + "/" + dbname


@pytest.fixture
def conn():
    """A fresh, migrated test database per test. Skips if Postgres isn't reachable."""
    try:
        admin = psycopg.connect(_url_for("postgres"), autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable (start it with: docker compose up -d postgres)")
    with admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {TEST_DB}")
    c = db.connect(_url_for(TEST_DB))
    db.migrate(c)
    db.seed_airlines(c)
    yield c
    c.close()
