from types import SimpleNamespace

import pytest
import requests

from at_ingest import opensky, store, worker
from at_ingest.filter import load_allowlist

ALLOW = load_allowlist()


def test_replay_shifts_times_to_now_and_loops():
    src = worker.ReplaySource()
    t, states = src.next_states(now=2_000_000_000)
    assert t == 2_000_000_000
    assert all(s[store.TIME_POSITION] == 2_000_000_000 for s in states)
    for _ in range(len(src.polls) - 1):
        src.next_states()
    _, again = src.next_states(now=2_000_000_000)  # wrapped around to the first poll
    assert [s[0] for s in again] == [s[0] for s in states]


def test_replay_writes_synthetic_aircraft(conn):
    src = worker.ReplaySource()
    for _ in range(60):
        src.poll(conn, ALLOW)
    seen = {r[0] for r in conn.execute("SELECT icao24 FROM aircraft_state")}
    assert {"f00001", "f00002", "f00003", "f00004"} <= seen
    assert conn.execute("SELECT count(*) FROM polls WHERE source = 'replay'").fetchone()[0] == 60


def _ok_response(credits):
    return opensky.StatesResponse(time=1_800_000_000, states=[], credits_remaining=credits, retry_after_s=None)


def _http_error(status, headers):
    resp = requests.Response()
    resp.status_code = status
    resp.headers.update(headers)
    resp.url = opensky.STATES_URL + "?lamin=1"
    return requests.HTTPError(response=resp)


@pytest.fixture
def src(monkeypatch):
    monkeypatch.setattr(opensky, "tokens_from_env", lambda: SimpleNamespace())
    return worker.OpenSkySource(reserve=40)


def test_normal_poll_keeps_cadence(conn, src, monkeypatch):
    monkeypatch.setattr(opensky, "fetch_states", lambda tokens: _ok_response(3000))
    assert src.poll(conn, ALLOW) == 0


def test_low_credits_pause_polling(conn, src, monkeypatch):
    monkeypatch.setattr(opensky, "fetch_states", lambda tokens: _ok_response(12))
    assert src.poll(conn, ALLOW) == worker.DEFAULT_BACKOFF_S


def test_rate_limit_honours_retry_after(conn, src, monkeypatch):
    def raise_429(tokens):
        raise _http_error(429, {"X-Rate-Limit-Retry-After-Seconds": "1234", "X-Rate-Limit-Remaining": "0"})
    monkeypatch.setattr(opensky, "fetch_states", raise_429)
    assert src.poll(conn, ALLOW) == 1234
    row = conn.execute("SELECT http_status, credits_remaining, error FROM polls").fetchone()
    assert row[0] == 429 and row[1] == 0 and "429" in row[2]


def test_network_error_is_recorded_not_raised(conn, src, monkeypatch):
    def boom(tokens):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(opensky, "fetch_states", boom)
    assert src.poll(conn, ALLOW) == worker.ERROR_RETRY_S
    assert conn.execute("SELECT error FROM polls").fetchone()[0] == "ConnectionError"
