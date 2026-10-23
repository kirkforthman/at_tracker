"""Write one poll (already filtered) to Postgres in a single transaction."""
from datetime import UTC, datetime, timedelta

# OpenSky state vector indexes (https://openskynetwork.github.io/opensky-api/rest.html).
ICAO24, CALLSIGN, TIME_POSITION, LAST_CONTACT, LON, LAT = 0, 1, 3, 4, 5, 6
BARO_ALT, ON_GROUND, VELOCITY, TRACK, VRATE, GEO_ALT, SQUAWK = 7, 8, 9, 10, 11, 13, 14

COLUMNS = ("icao24", "ts", "last_seen", "callsign", "lat", "lon", "baro_alt", "geo_alt",
           "velocity", "track", "vrate", "on_ground", "squawk")
POSITION_COLUMNS = tuple(c for c in COLUMNS if c != "last_seen")


def _ts(epoch):
    return datetime.fromtimestamp(epoch, UTC)


def rows_from_states(states):
    """Map kept state vectors to table rows; skip states without a position."""
    rows = []
    for s in states:
        if s[LAT] is None or s[LON] is None or s[TIME_POSITION] is None:
            continue
        rows.append((s[ICAO24], _ts(s[TIME_POSITION]), _ts(s[LAST_CONTACT] or s[TIME_POSITION]),
                     s[CALLSIGN].strip().upper(), s[LAT], s[LON], s[BARO_ALT], s[GEO_ALT],
                     s[VELOCITY], s[TRACK], s[VRATE], bool(s[ON_GROUND]), s[SQUAWK]))
    return rows


def partition_name(day):
    return f"positions_{day:%Y%m%d}"


def ensure_partition(conn, day):
    """Create the daily positions partition for `day` (a date) if it doesn't exist."""
    nxt = day + timedelta(days=1)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {partition_name(day)} PARTITION OF positions "
                 f"FOR VALUES FROM ('{day.isoformat()}') TO ('{nxt.isoformat()}')")


def write_poll(conn, *, source, states=(), received=None, unmatched=None, data_time=None,
               http_status=None, latency_ms=None, credits_remaining=None, error=None, now=None):
    """Record a poll and its kept states. Returns the poll id.

    `states` must already have passed filter_states(); this function trusts that.
    Failed polls are recorded too (with `error` set and no states).
    """
    now = now or datetime.now(UTC)
    rows = rows_from_states(states)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO polls (source, ts, data_time, http_status, received, kept, latency_ms, "
            "credits_remaining, error) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (source, now, _ts(data_time) if data_time else None, http_status, received,
             len(rows) if error is None else None, latency_ms, credits_remaining, error))
        poll_id = cur.fetchone()[0]

        if rows:
            for day in {r[1].date() for r in rows}:
                ensure_partition(conn, day)
            cur.execute(
                "CREATE TEMP TABLE incoming ("
                "icao24 text, ts timestamptz, last_seen timestamptz, callsign text, "
                "lat double precision, lon double precision, baro_alt real, geo_alt real, "
                "velocity real, track real, vrate real, on_ground boolean, squawk text"
                ") ON COMMIT DROP")
            with cur.copy(f"COPY incoming ({', '.join(COLUMNS)}) FROM STDIN") as copy:
                for r in rows:
                    copy.write_row(r)
            cols = ", ".join(POSITION_COLUMNS)
            cur.execute(f"INSERT INTO positions (poll_id, {cols}) SELECT %s, {cols} FROM incoming "
                        "ON CONFLICT DO NOTHING", (poll_id,))
            state_cols = ", ".join(COLUMNS)
            updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in (*COLUMNS[1:], "poll_id"))
            cur.execute(
                f"INSERT INTO aircraft_state (poll_id, {state_cols}) "
                f"SELECT DISTINCT ON (icao24) %s, {state_cols} FROM incoming ORDER BY icao24, ts DESC "
                f"ON CONFLICT (icao24) DO UPDATE SET {updates} "
                "WHERE aircraft_state.ts <= EXCLUDED.ts", (poll_id,))

        if unmatched:
            cur.executemany(
                "INSERT INTO unmatched_prefixes (day, prefix, count) VALUES (%s, %s, %s) "
                "ON CONFLICT (day, prefix) DO UPDATE SET count = unmatched_prefixes.count + EXCLUDED.count",
                [(now.date(), p, n) for p, n in unmatched.items()])
    return poll_id
