# Worklog

Short dated entries: what was done, what the agent got wrong, what was corrected.

## 2026-10-23 — P0 start
- Wrote the airline-only ingest filter (allowlist + military icao24 block) with 12 unit tests, the
  OpenSky client, and a probe that records filtered fixtures.
- First live CONUS poll (anonymous): 8,732 aircraft received, 3,487 airline kept. The planning
  estimate of 3–6k received was low; the airline count (~3.5k) is at the top of the 1.5–3k estimate,
  which raises the SVG rendering risk for P1.
- Top dropped airline-shaped prefixes were business-jet operators (EJA 195, LXJ 95); allowlist
  candidates to review: KAP (Cape Air, scheduled commuter), JSX (public charter).
- The callsign pattern in the planning doc (`\d{1,4}[A-Z]{0,2}`) was tightened to
  `\d[0-9A-Z]{0,4}` to accept alphanumeric flight ids like `BAW2KT`.
- Authenticated OpenSky check: first attempt returned 401 `unauthorized_client` (credentials
  mismatch, fixed by re-entering them). Two polls then confirmed **4 credits per CONUS call**
  (3,986 → 3,982), so 90 s polling uses 3,840 of 4,000/day. ~8,890 received, ~3,510 kept.
- After the WSL restart (23 GB visible, docker group active) the GPU is visible inside containers.
- gpt-oss-20b on llama.cpp CUDA (`--n-cpu-moe 6`, 16k context): smoke-test tool call passed in 1.3 s,
  10.5 / 12.3 GB VRAM, ~76 tok/s generation, ~185 tok/s prompt.
- Gap caught by the user: PLANNING.md mentioned the P0 LLM step only as one clause in the milestone
  table. Added a "P0 detail: the LLM" section with the setup, the P0-vs-P6 boundary and results.
- Before creating a public GitHub repo: replaced the recorded OpenSky/adsbdb fixtures with
  synthetic, labelled ones from a deterministic generator that also emits ground-truth legs for P3
  (rotation with turn + callsign change, first-seen-in-cruise, coverage gap, landing lost on
  final). The probe now writes real responses to gitignored `ingest/recordings/`. The unpushed P0
  commit was amended so recorded data never enters the published history.
- P0 close-out: public repo with CI and branch protection on `main`. Pinned known-good
  versions (ADR 0003): exact Python deps, CI actions by commit SHA, Python 3.14.4 in CI, and the
  tested llama.cpp build (b11804, digest recorded) and model revision + SHA-256, to be applied
  in compose.yaml in P1. Dependabot proposes monthly bumps. Allowlist: added KAP (Cape Air)
  and JSX after reviewing unmatched prefixes. **P0 complete.**

## 2026-10-23 — P1 live map
- Compose stack (Postgres 18.4, ingest, dashboard; LLM profile) with pinned images. SQL migrations,
  daily-partitioned positions, latest-state upserts via COPY, hourly retention.
- Bug found by the DB tests: non-autocommit psycopg connections turned `conn.transaction()` blocks
  into savepoints inside an implicit transaction, so `ON COMMIT DROP` temp tables leaked between
  polls. Fixed by using autocommit connections with explicit transaction blocks.
- Live: ~3,500 airline aircraft kept per poll; dashboard serves them with ETag/304 and dead-reckons
  airborne planes between polls. Replay mode drives an end-to-end CI smoke test.
- Compose `llm` reused the P0 model download: `llm-model` found the blob by hash and hard-linked it.

## 2026-10-24 — P1 24 h run
- 961 polls in 24 h, 0 errors, 0 HTTP 429, 3,836 credits used. No off-allowlist or US-military
  rows in any table. Raw positions measured at ~0.35 GB/day (2.23 M rows); steady state
  ~0.7–1.05 GB with 48 h retention. SVG rendering kept. Top unmatched prefixes reviewed (ASI, VAR, NDU, VJA
  confirmed non-passenger; stay excluded). **P1 complete.**
