"""Mock fleet: seeded generator, server-owned motion, and the chat stub.

The generator is a direct port of data/aircraft.js from the static wireframe,
including the same linear congruential RNG, so seed 42 yields the same fleet.

Motion is advanced lazily: every snapshot() call first moves the fleet forward
by the wall-clock seconds elapsed since the last advance (if motion is on).
That avoids a background thread and works under the Flask dev reloader.
"""
import re
import threading
import time

from .airports import AIRPORTS, BY_CODE

AIRLINES = {
    "UAL": "United", "DAL": "Delta", "AAL": "American", "SWA": "Southwest",
    "JBU": "JetBlue", "ASA": "Alaska", "FFT": "Frontier", "NKS": "Spirit",
    "SKW": "SkyWest", "FDX": "FedEx",
}
_AIRLINE_CODES = list(AIRLINES)
_TYPES = ["B738", "A320", "A321", "B739", "E175", "CRJ9", "B763", "A319", "B752", "B38M"]


class _LCG:
    """Same constants as the JS wireframe so the fleet matches on seed 42."""

    def __init__(self, seed):
        self.seed = seed

    def rnd(self):
        self.seed = (self.seed * 1664525 + 1013904223) % 4294967296
        return self.seed / 4294967296

    def pick(self, arr):
        return arr[int(self.rnd() * len(arr))]


def generate(seed=42, count=70):
    r = _LCG(seed)
    fleet = []
    for i in range(count):
        o = r.pick(AIRPORTS)
        d = r.pick(AIRPORTS)
        while d is o:
            d = r.pick(AIRPORTS)
        flight = r.rnd() < 0.68
        al = r.pick(_AIRLINE_CODES)
        num = 100 + int(r.rnd() * 8900)
        reg = "N" + str(100 + int(r.rnd() * 899)) + chr(65 + int(r.rnd() * 26)) + chr(65 + int(r.rnd() * 26))
        fleet.append({
            "id": f"ac{i}",
            "callsign": f"{al}{num}",
            "airline": al,
            "reg": reg,
            "type": r.pick(_TYPES),
            "status": "flight" if flight else "ground",
            "origin": o[0],
            "dest": d[0],
            "progress": (0.08 + r.rnd() * 0.84) if flight else 0.0,
            "alt": (24000 + int(r.rnd() * 17) * 1000) if flight else 0,
            "gs": (380 + int(r.rnd() * 140)) if flight else int(r.rnd() * 15),
            "squawk": str(1200 + int(r.rnd() * 6500)).zfill(4),
            "speedPerSec": 0.0004 + r.rnd() * 0.0003,  # progress units per second
        })
    return fleet


class Fleet:
    """Thread-safe owner of fleet state."""

    def __init__(self, seed=42, count=70, motion=True):
        self._lock = threading.Lock()
        self._aircraft = generate(seed, count)
        self._by_id = {a["id"]: a for a in self._aircraft}
        self.motion = motion
        self._last = time.monotonic()

    # ---- motion ----
    def _advance(self):
        now = time.monotonic()
        dt, self._last = now - self._last, now
        if not self.motion or dt <= 0:
            return
        for p in self._aircraft:
            if p["status"] != "flight":
                continue
            p["progress"] += p["speedPerSec"] * dt
            if p["progress"] >= 1:
                p["status"], p["progress"], p["alt"], p["gs"] = "ground", 0.0, 0, 0
                p["origin"], p["dest"] = p["dest"], p["origin"]

    def set_motion(self, enabled):
        with self._lock:
            self._advance()          # bank elapsed time under the old setting
            self.motion = bool(enabled)
            return self.motion

    # ---- reads ----
    def snapshot(self):
        with self._lock:
            self._advance()
            return [dict(a) for a in self._aircraft]

    def get(self, ac_id):
        with self._lock:
            self._advance()
            a = self._by_id.get(ac_id)
            return dict(a) if a else None

    # ---- chat stub ----
    def answer(self, q, selected=None):
        """Port of the wireframe's mock chat. Returns a structured reply:
        {"parts": [{"t": text} | {"link": id, "t": text}, ...], "focus": {"kind","id"} | None}
        """
        s = (q or "").strip()
        up = s.upper()
        text = lambda t: {"t": t}
        link = lambda i, t: {"link": i, "t": t}

        with self._lock:
            self._advance()
            fleet = self._aircraft
            ac = next((a for a in fleet if a["callsign"] == up or a["reg"] == up), None)
            if ac:
                where = (f"airborne {ac['origin']}→{ac['dest']}, FL{ac['alt'] // 100}"
                         if ac["status"] == "flight" else f"on the ground at {ac['origin']}")
                return {"parts": [text("Selected "), link(ac["id"], ac["callsign"]), text(f" — {where}.")],
                        "focus": {"kind": "aircraft", "id": ac["id"]}}
            if up in BY_CODE:
                return {"parts": [text("Showing "), link(up, up), text(f" ({BY_CODE[up][1]}).")],
                        "focus": {"kind": "airport", "id": up}}
            if re.search(r"ground", s, re.I):
                g = [a for a in fleet if a["status"] == "ground"]
                return {"parts": _listing(f"{len(g)} aircraft on the ground: ", g, link, text), "focus": None}
            if re.search(r"airborne|flight|flying", s, re.I):
                f = [a for a in fleet if a["status"] == "flight"]
                return {"parts": _listing(f"{len(f)} airborne: ", f, link, text), "focus": None}
            if re.search(r"help|\?$", s):
                return {"parts": [text("Try a callsign (e.g. UAL123), a tail number, an airport code (DEN), "
                                       "or “who is on the ground”.")], "focus": None}
            focus = "Nothing selected."
            if selected and selected.get("kind") == "aircraft" and selected.get("id") in self._by_id:
                focus = f"Current focus: {self._by_id[selected['id']]['callsign']}."
            elif selected and selected.get("kind") == "airport" and selected.get("id") in BY_CODE:
                focus = f"Current focus: {selected['id']}."
            return {"parts": [text("Flask stub: no real data source wired yet. " + focus)], "focus": None}


def _listing(prefix, items, link, text):
    parts = [text(prefix)]
    for i, a in enumerate(items[:8]):
        if i:
            parts.append(text(", "))
        parts.append(link(a["id"], a["callsign"]))
    if len(items) > 8:
        parts.append(text("…"))
    return parts
