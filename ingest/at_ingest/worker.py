"""Ingest worker: poll OpenSky (or replay synthetic data), filter, write to Postgres.

    python -m at_ingest.worker

Environment:
    INGEST_SOURCE    opensky (default) | replay
    POLL_INTERVAL_S  seconds between polls (default 90: 4 credits x 960/day = 3,840 of 4,000)
    CREDIT_RESERVE   pause OpenSky polling when remaining credits drop below this (default 40)
    OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET, POSTGRES_* or DATABASE_URL

Replay mode feeds tests/fixtures/opensky/synthetic_sequence.json through the same
filter and store path, shifted to the current time and looping, with no network.
"""
import copy
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv

from . import db, maintenance, opensky, store
from .filter import filter_states, load_allowlist

log = logging.getLogger("ingest")

REPLAY_FILE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "opensky" / "synthetic_sequence.json"
MAINTENANCE_EVERY_S = 3600
DEFAULT_BACKOFF_S = 3600     # when OpenSky asks us to stop but doesn't say for how long
ERROR_RETRY_S = 60


class OpenSkySource:
    name = "opensky"

    def __init__(self, reserve):
        self.tokens = opensky.tokens_from_env()
        self.reserve = reserve
        if not self.tokens:
            log.warning("no OpenSky credentials: polling anonymously (400 credits/day)")

    def poll(self, conn, allowlist):
        """One poll. Returns extra seconds to wait before the next one (0 = normal cadence)."""
        t0 = time.monotonic()
        try:
            resp = opensky.fetch_states(self.tokens)
        except requests.HTTPError as e:
            r = e.response
            retry = _int(r.headers.get("X-Rate-Limit-Retry-After-Seconds"))
            store.write_poll(conn, source=self.name, http_status=r.status_code,
                             latency_ms=_ms(t0), credits_remaining=_int(r.headers.get("X-Rate-Limit-Remaining")),
                             error=f"HTTP {r.status_code} from {r.url.split('?')[0]}")
            if r.status_code == 429:
                wait = retry or DEFAULT_BACKOFF_S
                log.warning("rate limited (429); waiting %ss", wait)
                return wait
            log.error("OpenSky HTTP %s", r.status_code)
            return ERROR_RETRY_S
        except requests.RequestException as e:
            store.write_poll(conn, source=self.name, latency_ms=_ms(t0), error=type(e).__name__)
            log.error("OpenSky request failed: %s", type(e).__name__)
            return ERROR_RETRY_S

        result = filter_states(resp.states, allowlist)
        store.write_poll(conn, source=self.name, states=result.kept, received=result.received,
                         unmatched=result.unmatched_prefixes, data_time=resp.time, http_status=200,
                         latency_ms=_ms(t0), credits_remaining=resp.credits_remaining)
        log.info("poll: received %d, kept %d, credits %s", result.received, len(result.kept),
                 resp.credits_remaining)
        if resp.credits_remaining is not None and resp.credits_remaining < self.reserve:
            wait = resp.retry_after_s or DEFAULT_BACKOFF_S
            log.warning("credits %d below reserve %d; pausing %ss", resp.credits_remaining, self.reserve, wait)
            return wait
        return 0


class ReplaySource:
    name = "replay"

    def __init__(self, path=REPLAY_FILE):
        self.polls = json.loads(Path(path).read_text())["polls"]
        self.i = 0

    def next_states(self, now=None):
        """The next synthetic poll, with timestamps shifted so it looks live. Loops forever."""
        now = int(now or time.time())
        p = self.polls[self.i % len(self.polls)]
        self.i += 1
        shift = now - p["time"]
        states = copy.deepcopy(p["states"])
        for s in states:
            s[store.TIME_POSITION] += shift
            s[store.LAST_CONTACT] += shift
        return now, states

    def poll(self, conn, allowlist):
        t, states = self.next_states()
        result = filter_states(states, allowlist)
        store.write_poll(conn, source=self.name, states=result.kept, received=result.received,
                         unmatched=result.unmatched_prefixes, data_time=t)
        log.info("replay poll %d: kept %d", self.i, len(result.kept))
        return 0


def _int(v):
    return int(v) if v is not None and str(v).isdigit() else None


def _ms(t0):
    return round((time.monotonic() - t0) * 1000)


def connect_with_retry(attempts=30, delay=2):
    for i in range(attempts):
        try:
            return db.connect()
        except psycopg.OperationalError:
            if i == attempts - 1:
                raise
            log.info("waiting for Postgres...")
            time.sleep(delay)


def run():
    interval = int(os.environ.get("POLL_INTERVAL_S", "90"))
    source_name = os.environ.get("INGEST_SOURCE", "opensky")
    source = ReplaySource() if source_name == "replay" else OpenSkySource(int(os.environ.get("CREDIT_RESERVE", "40")))
    allowlist = load_allowlist()

    conn = connect_with_retry()
    log.info("migrations applied: %s", db.migrate(conn) or "none pending")
    log.info("airlines seeded: %d", db.seed_airlines(conn))
    log.info("maintenance: %s", maintenance.run(conn))
    last_maintenance = time.monotonic()
    log.info("polling %s every %ss", source.name, interval)

    next_tick = time.monotonic()
    while True:
        extra = 0
        try:
            if conn.closed:
                conn = connect_with_retry()
            extra = source.poll(conn, allowlist)
            if time.monotonic() - last_maintenance >= MAINTENANCE_EVERY_S:
                log.info("maintenance: %s", maintenance.run(conn))
                last_maintenance = time.monotonic()
        except psycopg.Error as e:
            log.error("database error: %s; reconnecting", type(e).__name__)
            conn.close()
            extra = ERROR_RETRY_S
        next_tick = max(next_tick + interval, time.monotonic() + extra)
        time.sleep(max(0, next_tick - time.monotonic()))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # local runs; Compose passes env directly
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))       # PID 1 in a container ignores SIGTERM otherwise
    run()


if __name__ == "__main__":
    main()
