"""Read-only access to the ingest database for the dashboard (deterministic, no LLM).

The ingest worker owns the schema (ingest/migrations/). Values are stored in SI
units as OpenSky sends them and converted to aviation display units here.
"""
import os
from contextlib import contextmanager

import psycopg

VISIBLE_WINDOW = "5 minutes"     # aircraft not heard from for longer drop off the map
M_TO_FT, MS_TO_KT, MS_TO_FPM = 3.28084, 1.943844, 196.8504


def database_url():
    if url := os.environ.get("DATABASE_URL"):
        return url
    return "postgresql://{}:{}@{}:{}/{}".format(
        os.environ.get("POSTGRES_USER", "at_tracker"), os.environ.get("POSTGRES_PASSWORD", ""),
        os.environ.get("POSTGRES_HOST", "localhost"), os.environ.get("POSTGRES_PORT", "5432"),
        os.environ.get("POSTGRES_DB", "at_tracker"))


@contextmanager
def _conn():
    with psycopg.connect(database_url(), autocommit=True, connect_timeout=5) as c:
        yield c


_AIRCRAFT_SQL = f"""
    SELECT icao24, callsign, on_ground, lat, lon, baro_alt, geo_alt, velocity, track, vrate, squawk,
           extract(epoch FROM ts), extract(epoch FROM last_seen)
    FROM aircraft_state
    WHERE last_seen > now() - interval '{VISIBLE_WINDOW}'
"""


def _aircraft(row):
    icao24, cs, on_ground, lat, lon, baro, geo, vel, trk, vr, sq, ts, seen = row
    alt = baro if baro is not None else geo
    return {
        "id": icao24,
        "icao24": icao24,
        "callsign": cs,
        "airline": cs[:3],
        "status": "ground" if on_ground else "flight",
        "lat": lat,
        "lon": lon,
        "alt": round(alt * M_TO_FT) if alt is not None and not on_ground else 0,
        "gs": round(vel * MS_TO_KT) if vel is not None else None,
        "track": round(trk) if trk is not None else None,
        "vrate": round(vr * MS_TO_FPM) if vr is not None else None,
        "squawk": sq,
        "ts": float(ts),        # time of this position report
        "seen": float(seen),    # last contact
    }


def snapshot():
    with _conn() as c:
        return [_aircraft(r) for r in c.execute(_AIRCRAFT_SQL)]


def aircraft(ident):
    """One aircraft by icao24 or callsign (case-insensitive), or None."""
    ident = ident.strip()
    with _conn() as c:
        row = c.execute(_AIRCRAFT_SQL + " AND (icao24 = lower(%s) OR callsign = upper(%s)) "
                        "ORDER BY last_seen DESC LIMIT 1", (ident, ident)).fetchone()
    return _aircraft(row) if row else None


def airlines():
    """{icao: name} for the allowlisted airlines."""
    with _conn() as c:
        return dict(c.execute("SELECT icao, name FROM airlines ORDER BY icao"))


def latest_poll():
    """The most recent successful poll, or None."""
    with _conn() as c:
        row = c.execute("SELECT id, extract(epoch FROM ts), extract(epoch FROM data_time), kept, credits_remaining "
                        "FROM polls WHERE error IS NULL ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    pid, ts, data_time, kept, credits = row
    return {"id": pid, "ts": float(ts), "data_time": float(data_time) if data_time else None,
            "kept": kept, "credits_remaining": credits}
