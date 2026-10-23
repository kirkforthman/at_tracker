import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from at_ingest import db, maintenance, store
from at_ingest.filter import filter_states, is_airline, load_allowlist

FIXTURES = Path(__file__).parent / "fixtures" / "opensky"
ALLOW = load_allowlist()


def raw_poll():
    return json.loads((FIXTURES / "synthetic_raw_poll.json").read_text())


def write(conn, states, **kw):
    r = filter_states(states, ALLOW)
    return store.write_poll(conn, source="test", states=r.kept, received=r.received,
                            unmatched=r.unmatched_prefixes, **kw), r


def count(conn, sql):
    return conn.execute(sql).fetchone()[0]


def test_migrate_is_idempotent(conn):
    assert db.migrate(conn) == []
    assert count(conn, "SELECT count(*) FROM schema_migrations") >= 1


def test_airlines_seeded_from_allowlist(conn):
    assert count(conn, "SELECT count(*) FROM airlines") == len(ALLOW)


def test_only_kept_states_are_stored(conn):
    raw = raw_poll()
    poll_id, r = write(conn, raw["states"])
    assert count(conn, "SELECT count(*) FROM positions") == len(raw["expected"]["kept_icao24"])
    stored = {row[0] for row in conn.execute("SELECT icao24 FROM aircraft_state")}
    assert stored == set(raw["expected"]["kept_icao24"])
    for icao24, cs in conn.execute("SELECT icao24, callsign FROM positions"):
        assert is_airline(icao24, cs, ALLOW)
    row = conn.execute("SELECT received, kept FROM polls WHERE id = %s", (poll_id,)).fetchone()
    assert row == (raw["expected"]["received"], len(r.kept))


def test_repeated_poll_adds_no_duplicate_positions(conn):
    states = raw_poll()["states"]
    write(conn, states)
    n = count(conn, "SELECT count(*) FROM positions")
    write(conn, states)
    assert count(conn, "SELECT count(*) FROM positions") == n
    assert count(conn, "SELECT count(*) FROM polls") == 2


def test_state_keeps_latest_position(conn):
    states = raw_poll()["states"]
    newer = copy.deepcopy(states)
    for s in newer:
        s[store.TIME_POSITION] += 90
        s[store.LAST_CONTACT] += 90
        s[store.LAT] += 0.1
    write(conn, newer)
    write(conn, states)  # an older report arriving later must not overwrite
    icao24 = newer[0][0]
    lat = conn.execute("SELECT lat FROM aircraft_state WHERE icao24 = %s", (icao24,)).fetchone()[0]
    assert lat == newer[0][store.LAT]


def test_unmatched_prefix_counts_accumulate(conn):
    states = raw_poll()["states"]
    write(conn, states)
    write(conn, states)
    rows = dict(conn.execute("SELECT prefix, count FROM unmatched_prefixes"))
    assert rows == {"RCH": 2, "EJA": 2, "ZZZ": 2}


def test_failed_poll_is_recorded(conn):
    store.write_poll(conn, source="test", http_status=503, error="HTTP 503")
    assert conn.execute("SELECT http_status, kept, error FROM polls").fetchone() == (503, None, "HTTP 503")


def test_maintenance_creates_and_drops_partitions_and_prunes_state(conn):
    write(conn, raw_poll()["states"])  # synthetic data lands on its own day's partition
    data_day = conn.execute("SELECT min(ts)::date FROM positions").fetchone()[0]
    now = datetime.combine(data_day, datetime.min.time(), UTC) + timedelta(days=4)
    result = maintenance.run(conn, now=now)
    assert store.partition_name(data_day) in result["dropped"]
    assert count(conn, "SELECT count(*) FROM positions") == 0
    assert result["pruned_aircraft"] == len(raw_poll()["expected"]["kept_icao24"])
    parts = {r[0] for r in conn.execute(
        "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid")}
    assert store.partition_name(now.date()) in parts
    assert store.partition_name(now.date() + timedelta(days=1)) in parts
