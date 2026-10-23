"""OpenSky REST client: OAuth2 client-credentials token + bounded /states/all."""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
STATES_URL = "https://opensky-network.org/api/states/all"

# CONUS bounding box, derived from the state geometry the dashboard draws
# (dashboard/static/geo/states.json, non-CONUS states excluded), padded ~1 degree
# so aircraft just offshore or over the border still appear on the map.
CONUS_BBOX = {"lamin": 23.5, "lomin": -125.8, "lamax": 50.4, "lomax": -65.9}

# How many seconds before expiry to proactively refresh the token.
TOKEN_REFRESH_MARGIN = 30
TIMEOUT_S = 30


class TokenManager:
    """OAuth2 client-credentials token with automatic refresh."""

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.expires_at = None

    def get_token(self):
        """Return a valid access token, refreshing automatically if needed."""
        if self.token and self.expires_at and datetime.now() < self.expires_at:
            return self.token
        return self._refresh()

    def _refresh(self):
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=TIMEOUT_S,
        )
        r.raise_for_status()
        data = r.json()
        self.token = data["access_token"]
        expires_in = data.get("expires_in", 1800)
        self.expires_at = datetime.now() + timedelta(seconds=expires_in - TOKEN_REFRESH_MARGIN)
        return self.token

    def headers(self):
        return {"Authorization": f"Bearer {self.get_token()}"}


def tokens_from_env():
    """TokenManager from OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET, or None for anonymous."""
    cid, secret = os.environ.get("OPENSKY_CLIENT_ID"), os.environ.get("OPENSKY_CLIENT_SECRET")
    return TokenManager(cid, secret) if cid and secret else None


@dataclass
class StatesResponse:
    time: int
    states: list
    credits_remaining: int | None
    retry_after_s: int | None


def _int_header(headers, name):
    v = headers.get(name)
    return int(v) if v is not None and v.isdigit() else None


def fetch_states(tokens=None, bbox=CONUS_BBOX):
    """One /states/all call. Raw, unfiltered: pass .states through filter_states() before storing."""
    headers = tokens.headers() if tokens else {}
    r = requests.get(STATES_URL, params=bbox, headers=headers, timeout=TIMEOUT_S)
    r.raise_for_status()
    body = r.json()
    return StatesResponse(
        time=body.get("time"),
        states=body.get("states") or [],
        credits_remaining=_int_header(r.headers, "X-Rate-Limit-Remaining"),
        retry_after_s=_int_header(r.headers, "X-Rate-Limit-Retry-After-Seconds"),
    )
