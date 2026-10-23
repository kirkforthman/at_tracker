"""Source probe: call each external source once and save the response locally.

    python -m at_ingest.probe opensky [--polls 2]   # 2+ polls measures credits per CONUS call
    python -m at_ingest.probe faa metar adsbdb ourairports
    python -m at_ingest.probe all

Responses go to ingest/recordings/ (gitignored): real data is never committed.
Committed test fixtures are synthetic (tests/fixtures/generate_synthetic.py).
OpenSky responses still go through filter_states() before anything is written,
so even local recordings only contain allowlisted airline traffic.
"""
import argparse
import csv
import io
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

from . import opensky
from .filter import filter_states, load_allowlist

RECORDINGS = Path(__file__).resolve().parents[1] / "recordings"
FAA_URL = "https://nasstatus.faa.gov/api/airport-status-information"
METAR_URL = "https://aviationweather.gov/api/data/metar"
ADSBDB_URL = "https://api.adsbdb.com/v0/callsign/{}"
OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
POLL_INTERVAL_S = 15  # spacing between OpenSky probe calls; the credit cost is per call, not per second
TIMEOUT_S = 30


def _stamp():
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _save(source, name, content):
    path = RECORDINGS / source / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content, indent=1))
    print(f"  saved {path.relative_to(RECORDINGS.parent)}")


def probe_opensky(polls):
    tokens = opensky.tokens_from_env()
    print(f"opensky: {'authenticated' if tokens else 'ANONYMOUS (set OPENSKY_CLIENT_ID/SECRET in .env)'}")
    allowlist = load_allowlist()
    credits = []
    for i in range(polls):
        if i:
            time.sleep(POLL_INTERVAL_S)
        resp = opensky.fetch_states(tokens)
        result = filter_states(resp.states, allowlist)
        credits.append(resp.credits_remaining)
        print(f"  poll {i + 1}: received {result.received}, kept {len(result.kept)}, "
              f"credits remaining {resp.credits_remaining}")
        _save("opensky", f"states_{_stamp()}.json", {
            "time": resp.time,
            "states": result.kept,
            "_filter": {"received": result.received, "kept": len(result.kept),
                        "unmatched_prefixes": dict(result.unmatched_prefixes.most_common())},
        })
    known = [c for c in credits if c is not None]
    if len(known) >= 2:
        per_call = (known[0] - known[-1]) / (len(known) - 1)
        print(f"  credits per CONUS call: {per_call:g} -> 90 s polling uses {per_call * 960:g}/day")


def probe_faa():
    r = requests.get(FAA_URL, timeout=TIMEOUT_S)
    r.raise_for_status()
    print(f"faa: {len(r.content)} bytes")
    _save("faa", f"airport_status_{_stamp()}.xml", r.text)


def probe_metar(ids="KIAD,KATL,KJFK,KORD,KDEN,KSFO"):
    r = requests.get(METAR_URL, params={"ids": ids, "format": "json"}, timeout=TIMEOUT_S)
    r.raise_for_status()
    print(f"metar: {len(r.json())} reports for {ids}")
    _save("metar", f"metar_{_stamp()}.json", r.json())


def probe_adsbdb(callsigns=("UAL1", "DAL1", "SWA1")):
    for cs in callsigns:
        r = requests.get(ADSBDB_URL.format(cs), timeout=TIMEOUT_S)
        print(f"adsbdb {cs}: HTTP {r.status_code}")
        if r.ok:
            _save("adsbdb", f"callsign_{cs}.json", r.json())


def probe_ourairports():
    # Too large to commit (~12 MB); record shape only. Loaded at runtime in P2.
    r = requests.get(OURAIRPORTS_URL, timeout=TIMEOUT_S)
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.text)))
    us = [x for x in rows if x["iso_country"] == "US" and x["type"] in ("large_airport", "medium_airport")]
    print(f"ourairports: {len(rows)} rows, {len(us)} US large/medium; columns: {', '.join(rows[0])}")


def main():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+", choices=["opensky", "faa", "metar", "adsbdb", "ourairports", "all"])
    ap.add_argument("--polls", type=int, default=2, help="OpenSky calls to make (>=2 measures credit cost)")
    args = ap.parse_args()
    sources = {"opensky", "faa", "metar", "adsbdb", "ourairports"} if "all" in args.sources else set(args.sources)
    if "opensky" in sources:
        probe_opensky(args.polls)
    if "faa" in sources:
        probe_faa()
    if "metar" in sources:
        probe_metar()
    if "adsbdb" in sources:
        probe_adsbdb()
    if "ourairports" in sources:
        probe_ourairports()


if __name__ == "__main__":
    main()
