"""
OpenSky live-data collector: STARTING POINT, NOT WIRED.

This file is the seed for the collector half of the project. Today it does one
thing: authenticate against OpenSky with OAuth2 client credentials and fetch a
single /states/all snapshot. Nothing here talks to the dashboard yet.

The plan, in general direction only (specifics to be elaborated before action):

  1. COLLECTOR (this file, eventually a long-running process on the target box)
     - Poll OpenSky /states/all on a fixed cadence, restricted to the CONUS
       bounding box so each call costs fewer credits than a worldwide pull.
     - Normalize each state vector into the shape the dashboard already
       expects (see dashboard/conus/fleet.py: id, callsign, status, origin,
       dest, progress, alt, gs, squawk ...). Some fields have no OpenSky
       equivalent (origin/dest/progress); those need a routing source or
       get dropped from the readout.
     - Write snapshots to a shared store. Candidates: SQLite for a single
       box, or Redis/Postgres if collector and dashboard end up on separate
       hosts. Decide after the hardware target is known.

  2. DASHBOARD (dashboard/, the Flask app)
     - Replace the mock Fleet in dashboard/conus/fleet.py with an adapter
       that reads the latest snapshot from the store. The Flask routes and
       the browser code should not need to change; /api/aircraft keeps its
       contract {ts, motion, aircraft: [...]}.
     - The "motion" toggle becomes meaningless with live data; either remove
       it or repurpose it as "pause updates".

  3. OPERATIONS
     - Credentials come from environment variables or a secrets file outside
       the repo. Never commit real CLIENT_ID / CLIENT_SECRET.
     - Budget: OpenSky credits per day are limited. Pick the poll interval
       from the credit cost per call (read X-Rate-Limit-Remaining, printed
       below) and the daily allowance, with headroom.
     - This will be migrated to different hardware. Keep the collector free
       of host-specific paths and run it under a supervisor (systemd,
       launchd) there, not from a Desktop folder.

Run this file standalone to measure the credit cost of one CONUS call:
    uv run --no-project --with requests python testing.py
Run it twice; the drop in X-Rate-Limit-Remaining is the per-call cost.
"""

import requests
from datetime import datetime, timedelta

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
STATES_URL = "https://opensky-network.org/api/states/all"

# Placeholders. Move to environment variables before this becomes a service.
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"

# CONUS bounding box, derived from the state geometry the dashboard draws
# (dashboard/static/geo/states.json, non-CONUS states excluded), padded ~1 degree
# so aircraft just offshore or over the border still appear on the map.
CONUS_BBOX = {"lamin": 23.5, "lomin": -125.8, "lamax": 50.4, "lomax": -65.9}

# How many seconds before expiry to proactively refresh the token.
TOKEN_REFRESH_MARGIN = 30


class TokenManager:
    """OAuth2 client-credentials token with automatic refresh.

    Keep this as-is when the collector becomes a service; it already handles
    the refresh cycle the poller will need.
    """

    def __init__(self):
        self.token = None
        self.expires_at = None

    def get_token(self):
        """Return a valid access token, refreshing automatically if needed."""
        if self.token and self.expires_at and datetime.now() < self.expires_at:
            return self.token
        return self._refresh()

    def _refresh(self):
        """Fetch a new access token from the OpenSky authentication server."""
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        r.raise_for_status()

        data = r.json()
        self.token = data["access_token"]
        expires_in = data.get("expires_in", 1800)
        self.expires_at = datetime.now() + timedelta(seconds=expires_in - TOKEN_REFRESH_MARGIN)
        return self.token

    def headers(self):
        """Return request headers with a valid Bearer token."""
        return {"Authorization": f"Bearer {self.get_token()}"}


# Create a single shared instance for your script.
tokens = TokenManager()

# One snapshot, CONUS only. In the service version this becomes the body of a
# poll loop: fetch, normalize, write to the store, sleep until the next tick.
response = requests.get(STATES_URL, params=CONUS_BBOX, headers=tokens.headers())
response.raise_for_status()

# Diagnostics only. The state-vector field order is documented at
# https://openskynetwork.github.io/opensky-api/rest.html#all-state-vectors
print("status:", response.status_code)
print("aircraft in response:", len(response.json().get("states") or []))
for h in ("X-Rate-Limit-Remaining", "X-Rate-Limit-Retry-After-Seconds"):
    print(f"{h}: {response.headers.get(h)}")
