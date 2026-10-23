"""Ingest filter: keep airline traffic, drop everything else before it is stored.

OpenSky returns every aircraft in the bounding box and has no server-side filter
by operator, so this runs in memory on each response, before anything is written
to the database, logs or fixtures. Dropped state vectors leave behind only
counts: how many were received, and how many per unmatched callsign prefix.

A state vector is kept only if all of these hold:
  1. the callsign is airline-shaped (3-letter ICAO prefix + flight number),
  2. the prefix is on the airline allowlist (data/airlines.csv),
  3. the icao24 address is outside every blocked range (US military block).

The allowlist matters more than the pattern: military transports (RCH, CNV)
and business-jet charters (EJA, LXJ) also use 3-letter prefixes.
"""
import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# ICAO flight ids: 3-letter operator prefix, then a number that may carry
# trailing letters (UAL1234, DAL12A, BAW2KT). OpenSky pads callsigns with spaces.
CALLSIGN_RE = re.compile(r"^([A-Z]{3})(\d[0-9A-Z]{0,4})$")

# Inclusive icao24 ranges that are never kept, regardless of callsign.
BLOCKED_ICAO24_RANGES = [
    (0xAE0000, 0xAFFFFF),  # US military
]

AIRLINES_CSV = Path(__file__).parent / "data" / "airlines.csv"

# OpenSky /states/all state vector indexes.
# https://openskynetwork.github.io/opensky-api/rest.html#all-state-vectors
ICAO24, CALLSIGN = 0, 1


def load_allowlist(path=AIRLINES_CSV):
    """Return the set of allowlisted ICAO airline prefixes."""
    with open(path, newline="") as f:
        return {row["icao"] for row in csv.DictReader(f)}


def normalize_callsign(raw):
    return (raw or "").strip().upper()


def callsign_prefix(callsign):
    """'UAL1234' -> 'UAL'; None if the callsign is not airline-shaped."""
    m = CALLSIGN_RE.match(callsign)
    return m.group(1) if m else None


def icao24_blocked(icao24):
    try:
        addr = int(icao24, 16)
    except (TypeError, ValueError):
        return True  # unparseable address: drop rather than guess
    return any(lo <= addr <= hi for lo, hi in BLOCKED_ICAO24_RANGES)


def is_airline(icao24, callsign, allowlist):
    prefix = callsign_prefix(normalize_callsign(callsign))
    return prefix is not None and prefix in allowlist and not icao24_blocked(icao24)


@dataclass
class FilterResult:
    kept: list
    received: int
    # Airline-shaped prefixes that were dropped because they are not on the
    # allowlist. Prefix and count only, used to spot airlines missing from it.
    unmatched_prefixes: Counter = field(default_factory=Counter)

    @property
    def dropped(self):
        return self.received - len(self.kept)


def filter_states(states, allowlist):
    """Filter OpenSky state vectors down to allowlisted airline traffic."""
    states = states or []
    kept, unmatched = [], Counter()
    for s in states:
        if is_airline(s[ICAO24], s[CALLSIGN], allowlist):
            kept.append(s)
            continue
        prefix = callsign_prefix(normalize_callsign(s[CALLSIGN]))
        if prefix and prefix not in allowlist:
            unmatched[prefix] += 1
    return FilterResult(kept=kept, received=len(states), unmatched_prefixes=unmatched)
