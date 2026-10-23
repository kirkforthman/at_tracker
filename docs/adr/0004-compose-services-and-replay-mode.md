# 0004 — Compose services, replay mode, verified model fetch

Date: 2026-10-23 · Status: accepted

## Context
P1 introduces the first long-running services. They have to run the same way on this desktop, in
CI and on other hosts (ADR 0001), and CI can't use OpenSky: there are no credentials there, and
recorded data can't be committed (ADR 0002).

## Decision
- **One `compose.yaml`** with `postgres`, `ingest` and `dashboard`. The LLM is behind the
  `gpu-nvidia` profile. Ports are bound to `127.0.0.1`; data lives in named volumes; images are
  pinned by tag + digest (ADR 0003).
- **Containers run from source**, not an installed package, so `migrations/` and the replay fixture
  resolve the same way inside and outside Docker.
- **Schema migrations are plain SQL** (`ingest/migrations/NNN_*.sql`), applied in order by the
  worker at startup and recorded in `schema_migrations`. No migration framework.
- **Replay mode** (`INGEST_SOURCE=replay`) feeds the synthetic fixture sequence through the same
  filter and store code as live polling, with timestamps shifted to now, looping. CI's
  `compose-smoke` job runs the full stack this way and checks the dashboard serves only airline
  traffic. The same mode gives an offline demo.
- **Model weights are fetched by a one-shot `llm-model` service** that downloads a pinned Hugging
  Face revision and verifies its SHA-256 before `llm` starts. If a file with the right hash already
  exists in the volume, it is hard-linked instead of downloaded again.

## Consequences
- `docker compose up` is the only way the services need to be started, on any host.
- Replay data passes through the real code paths, so the end-to-end test is meaningful without
  network access.
- Changing the model means changing two pinned values (URL revision and hash) in `compose.yaml`.
