# at_tracker

Live map of airline traffic over the continental US, with a focus panel and a chat pane backed by a
local LLM. Work in progress: P1 (live map from OpenSky via Postgres).

    cp .env.example .env            # add OpenSky API credentials
    docker compose up -d --build    # then http://localhost:8080

Without credentials, `INGEST_SOURCE=replay docker compose up -d` runs on synthetic data.

    dashboard/   Flask app serving the D3 map, currently on a mock fleet
                 (see dashboard/README.md to run it)
    compose.yaml postgres, ingest, dashboard; local LLM behind the gpu-nvidia profile
    ingest/      worker: OpenSky polling, airline-only filter, Postgres schema + migrations, replay mode
    scripts/     dev setup (Docker Engine + NVIDIA toolkit), model fetch, smoke tests
    docs/        ADRs, per-milestone plans, worklog

Only airline traffic is stored: private, business and military aircraft are dropped in memory
before anything is written (docs/adr/0002-airline-traffic-only.md). Test fixtures for aircraft data
are synthetic (ingest/tests/fixtures/README.md); no recorded OpenSky data is committed.

This directory is meant to be moved to other hardware. Do not add machine-specific paths, and keep
credentials out of the tree (copy `.env.example` to `.env`).
