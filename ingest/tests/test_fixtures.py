import importlib.util
import itertools
import json
from pathlib import Path

from at_ingest.filter import filter_states, is_airline, load_allowlist

FIXTURES = Path(__file__).parent / "fixtures"
ALLOW = load_allowlist()


def _generator():
    spec = importlib.util.spec_from_file_location("generate_synthetic", FIXTURES / "generate_synthetic.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_committed_synthetic_fixtures_match_generator():
    for path, content in _generator().render().items():
        assert path.read_text() == content, f"{path.name} is stale: rerun generate_synthetic.py"


def test_no_unlabelled_files_in_aircraft_fixture_dirs():
    # Only synthetic data may live where aircraft-level data goes.
    for sub in ("opensky", "adsbdb"):
        for f in (FIXTURES / sub).glob("*.json"):
            doc = json.loads(f.read_text())
            assert doc.get("_synthetic") is True, f"{f} is not marked synthetic"


def test_sequence_contains_only_airline_traffic():
    seq = json.loads((FIXTURES / "opensky" / "synthetic_sequence.json").read_text())
    states = [s for p in seq["polls"] for s in p["states"]]
    assert states and all(is_airline(s[0], s[1], ALLOW) for s in states)


def test_sequence_polls_are_90s_apart():
    seq = json.loads((FIXTURES / "opensky" / "synthetic_sequence.json").read_text())
    times = [p["time"] for p in seq["polls"]]
    assert all(b - a == 90 for a, b in itertools.pairwise(times))


def test_raw_poll_filter_result_matches_expected():
    raw = json.loads((FIXTURES / "opensky" / "synthetic_raw_poll.json").read_text())
    r = filter_states(raw["states"], ALLOW)
    assert [s[0] for s in r.kept] == raw["expected"]["kept_icao24"]
    assert r.received == raw["expected"]["received"]
    assert dict(r.unmatched_prefixes) == raw["expected"]["unmatched_prefixes"]
