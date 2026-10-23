"""End-to-end check of a running Compose stack in replay mode (used by CI).

    INGEST_SOURCE=replay POLL_INTERVAL_S=2 docker compose up -d --build
    python3 scripts/compose_smoke.py

Passes when the dashboard reports a healthy DB with recent polls and serves the
synthetic aircraft, every one of which passes the airline-only filter.
Standard library only (plus the filter module, which is stdlib too).
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))
from at_ingest.filter import is_airline, load_allowlist

BASE = "http://localhost:8080"
TIMEOUT_S = 180
EXPECTED = {"f00001", "f00002", "f00004"}  # airborne or on the ground in the first replay polls


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.load(r)


def wait_for(what, check):
    deadline = time.monotonic() + TIMEOUT_S
    last = None
    while time.monotonic() < deadline:
        try:
            if result := check():
                print(f"ok: {what}")
                return result
        except (OSError, ValueError, KeyError, TypeError) as e:  # still starting: retry until the deadline
            last = e
        time.sleep(2)
    sys.exit(f"FAIL: timed out waiting for {what} (last error: {last!r})")


def main():
    wait_for("dashboard healthy with a recent poll",
             lambda: (h := get("/api/health"))["db_ok"] and h["last_poll_age_s"] is not None and h["last_poll_age_s"] < 30)
    aircraft = wait_for("synthetic aircraft served",
                        lambda: (a := get("/api/aircraft")["aircraft"]) and EXPECTED <= {x["id"] for x in a} and a)
    allow = load_allowlist()
    bad = [a["callsign"] for a in aircraft if not is_airline(a["icao24"], a["callsign"], allow)]
    if bad:
        sys.exit(f"FAIL: non-airline aircraft served: {bad}")
    print(f"ok: {len(aircraft)} aircraft, all airline traffic")


if __name__ == "__main__":
    main()
