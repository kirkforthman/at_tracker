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
| 5 | CI: push runs on `main` only; DB tests against a Postgres service; `compose-smoke` job (replay) | done, pending first CI run |
| 6 | Rendering measurement with ~3.5k planes (`?perf`); canvas only if > ~30 ms/frame | pending (needs a browser) |
| 7 | 24 h live run: credits ≤ 3,840/day, no 429s, airline-only check on all tables, volumes → PLANNING.md §6 | pending |

## Exit criteria
- Map shows live CONUS airline traffic, refreshing every 90 s.
- No non-allowlisted callsign anywhere in the DB.
- 24 h run under the credit budget; volumes measured and the estimates updated.
