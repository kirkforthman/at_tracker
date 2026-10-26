# P1 — Live map

Goal: an ingest worker polls OpenSky every 90 s and writes airline-only positions to Postgres, and
the dashboard shows them live instead of the mock fleet.

Decisions:
- Smooth motion: the browser dead-reckons airborne planes between polls.
- SVG first: measure rendering with real traffic, and switch the plane layer to canvas only if it's slow.
- Pinned images (ADR 0003); Compose services and replay mode (ADR 0004).

## Steps
| # | Step | Status |
|---|---|---|
| 1 | `compose.yaml` (Postgres 18.4 pinned), SQL migrations, `store.py` (COPY + upserts), `maintenance.py` (partitions, retention), DB tests | done |
| 2 | `worker.py`: live polling with budget guard (429 / reserve), replay mode; live run checked | done |
| 3 | Dashboard reads Postgres (`conus/store.py`), ETag/304, `/api/health`, deterministic chat stub; front end on real lat/lon + track, dead reckoning, pause + freshness badge, screen-distance picker | done |
| 4 | LLM in Compose (`gpu-nvidia` profile): pinned image, `llm-model` fetch + SHA-256 verify (reused P0 download); smoke test passed | done |
| 5 | CI: push runs on `main` only; DB tests against a Postgres service; `compose-smoke` job (replay) | done |
| 6 | Rendering measurement with ~3.5k planes (`?perf`); canvas only if > ~30 ms/frame | done: no sluggishness in use at peak traffic, SVG kept (frame times not recorded) |
| 7 | 24 h live run: credits ≤ 3,840/day, no 429s, airline-only check on all tables, volumes → PLANNING.md §6 | done (see Results) |

## Exit criteria
- Map shows live CONUS airline traffic, refreshing every 90 s.
- No non-allowlisted callsign anywhere in the DB.
- 24 h run under the credit budget; volumes measured and the estimates updated.

## Results (24 h run, 2026-10-23 20:50 → 2026-10-24 20:50 UTC, `main` @ 3931e48)
- 961 polls, 0 errors, 0 HTTP 429, no gap over 120 s (interval 78–101 s, avg 90.0 s).
- Credits used 3,836 of 4,000 (959 drops of exactly 4; the daily reset fell at 13:31 UTC; lowest balance 1,258).
- Airline-only: 0 rows in `positions` or `aircraft_state` whose callsign prefix is off the allowlist,
  0 in the US-military icao24 block, 0 with a non-airline callsign shape.
- Kept per poll: avg 2,455, max 3,679, min 520 (hourly avg 550 at 08 UTC to 3,612 at 22 UTC).
- Raw positions: 2.23 M rows/day, ~157 B/row including indexes, ≈ 0.35 GB/day. With 48 h retention
  on daily partitions, 2–3 partitions exist at once: ~0.7–1.05 GB steady state, inside the estimate.
- 8,021 distinct aircraft and 25,695 callsigns over the day; `aircraft_state` 8,063 rows (12 MB).
- First live partition drop at 2026-10-26 00:21 UTC: `positions_20261023` (88 MB) dropped, oldest
  position now 2026-10-24 00:00 UTC, positions total 700 → 634 MB, polling uninterrupted.
- Allowlist review of the largest unmatched prefixes: EJA, CXK, LXJ (business jet), CAP and
  ASI, VAR, NDU, VJA confirmed as not public passenger service and stay excluded. No allowlist change.

**P1 complete.**
