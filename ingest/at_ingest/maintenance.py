"""Retention: keep positions partitions current, drop old ones, prune stale aircraft."""
import re
from datetime import UTC, datetime, timedelta

from .store import ensure_partition

POSITIONS_RETENTION = timedelta(hours=48)
STATE_RETENTION = timedelta(hours=24)
_PARTITION_RE = re.compile(r"^positions_(\d{8})$")  # see store.partition_name


def run(conn, now=None):
    """Create today's and tomorrow's partitions, drop expired ones, prune aircraft_state.

    A daily partition is dropped once its whole day is older than the retention
    window, so up to 48 h + 1 day of positions exist just before a drop.
    """
    now = now or datetime.now(UTC)
    today = now.date()
    dropped = []
    with conn.transaction():
        ensure_partition(conn, today)
        ensure_partition(conn, today + timedelta(days=1))
        cutoff = now - POSITIONS_RETENTION
        parts = conn.execute(
            "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
            "JOIN pg_class p ON p.oid = i.inhparent WHERE p.relname = 'positions'").fetchall()
        for (name,) in parts:
            m = _PARTITION_RE.match(name)
            if not m:
                continue
            day_end = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=UTC) + timedelta(days=1)
            if day_end <= cutoff:
                conn.execute(f"DROP TABLE {name}")
                dropped.append(name)
        pruned = conn.execute("DELETE FROM aircraft_state WHERE last_seen < %s",
                              (now - STATE_RETENTION,)).rowcount
    return {"dropped": sorted(dropped), "pruned_aircraft": pruned}
