"""Deterministic chat stub over the live data, until the LLM agent arrives in P6.

Returns the structured reply the browser expects:
    {"parts": [{"t": text} | {"link": id, "t": text}, ...], "focus": {"kind", "id"} | None}
"""
import math
import re

from . import store
from .airports import BY_CODE

NEAR_AIRPORT_KM = 40


def text(t):
    return {"t": t}


def link(i, t):
    return {"link": i, "t": t}


def km_between(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def answer(q, selected=None):
    s = (q or "").strip()
    up = s.upper()

    if up in BY_CODE:
        code, name, lat, lon = BY_CODE[up]
        near = [a for a in store.snapshot() if km_between(lat, lon, a["lat"], a["lon"]) <= NEAR_AIRPORT_KM]
        ground = sum(a["status"] == "ground" for a in near)
        return {"parts": [text("Showing "), link(code, code),
                          text(f" ({name}): {ground} on the ground and {len(near) - ground} airborne "
                               f"within {NEAR_AIRPORT_KM} km.")],
                "focus": {"kind": "airport", "id": code}}

    if re.fullmatch(r"[A-Za-z0-9]{3,8}", s) and (ac := store.aircraft(s)):
        where = (f"airborne at {ac['alt']:,} ft, {ac['gs']} kt" if ac["status"] == "flight" else "on the ground")
        return {"parts": [text("Selected "), link(ac["id"], ac["callsign"]), text(f": {where}.")],
                "focus": {"kind": "aircraft", "id": ac["id"]}}

    if re.search(r"ground|airborne|flying|how many|count", s, re.IGNORECASE):
        fleet = store.snapshot()
        ground = sum(a["status"] == "ground" for a in fleet)
        return {"parts": [text(f"{len(fleet) - ground:,} airline aircraft airborne and {ground:,} on the ground "
                               "over the continental US right now.")], "focus": None}

    if re.search(r"help|\?$", s):
        return {"parts": [text("Try a callsign (e.g. UAL1234), an airport code (DEN), or \"how many are airborne\". "
                               "Full natural-language chat arrives with the local LLM.")], "focus": None}

    return {"parts": [text("I can look up a callsign, an airport code, or counts for now. "
                           "Natural-language answers arrive with the local LLM.")], "focus": None}
