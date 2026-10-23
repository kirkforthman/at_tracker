from at_ingest.filter import (
    callsign_prefix,
    filter_states,
    icao24_blocked,
    is_airline,
    load_allowlist,
)

ALLOW = load_allowlist()


def sv(icao24, callsign):
    """Minimal OpenSky state vector: only icao24 and callsign are read by the filter."""
    return [icao24, callsign, "United States", 0, 0, -77.0, 38.9, 10000.0, False, 230.0, 90.0, 0.0, None, 10100.0, "1234", False, 0]


def test_allowlist_loads_core_carriers():
    assert {"UAL", "DAL", "AAL", "SWA", "SKW", "FDX", "UPS", "KAP", "JSX"} <= ALLOW


def test_allowlist_excludes_military_and_charter_prefixes():
    assert not {"RCH", "CNV", "PAT", "EJA", "LXJ"} & ALLOW


def test_callsign_prefix():
    assert callsign_prefix("UAL1234") == "UAL"
    assert callsign_prefix("DAL12A") == "DAL"
    assert callsign_prefix("BAW2KT") == "BAW"
    assert callsign_prefix("N123AB") is None   # GA tail-number callsign
    assert callsign_prefix("UALX") is None     # no flight number
    assert callsign_prefix("") is None


def test_airline_kept_with_opensky_padding():
    assert is_airline("a1b2c3", "UAL1234 ", ALLOW)
    assert is_airline("a1b2c3", "skw5432", ALLOW)  # case-insensitive


def test_ga_dropped():
    assert not is_airline("a1b2c3", "N123AB  ", ALLOW)


def test_empty_callsign_dropped():
    assert not is_airline("a1b2c3", "", ALLOW)
    assert not is_airline("a1b2c3", None, ALLOW)


def test_military_callsign_dropped():
    assert not is_airline("a1b2c3", "RCH123", ALLOW)


def test_bizjet_charter_dropped():
    assert not is_airline("a1b2c3", "EJA456", ALLOW)


def test_military_icao24_block_dropped_even_with_airline_callsign():
    assert icao24_blocked("ae1234")
    assert icao24_blocked("AFFFFF")
    assert not icao24_blocked("adffff")
    assert not is_airline("ae1234", "UAL1234", ALLOW)


def test_unparseable_icao24_dropped():
    assert icao24_blocked("zzzzzz")
    assert icao24_blocked(None)


def test_filter_states_counts_and_unmatched_prefixes():
    states = [
        sv("a1b2c3", "UAL1234 "),
        sv("a1b2c4", "DAL56   "),
        sv("a1b2c5", "N123AB  "),
        sv("ae0001", "RCH123  "),
        sv("a1b2c6", "EJA456  "),
        sv("a1b2c7", "EJA789  "),
        sv("ae0002", "UAL99   "),
    ]
    r = filter_states(states, ALLOW)
    assert [s[1].strip() for s in r.kept] == ["UAL1234", "DAL56"]
    assert r.received == 7
    assert r.dropped == 5
    # Only airline-shaped prefixes that are off the allowlist are counted; no identifiers.
    assert r.unmatched_prefixes == {"RCH": 1, "EJA": 2}


def test_filter_states_handles_null_states():
    r = filter_states(None, ALLOW)
    assert r.kept == [] and r.received == 0
