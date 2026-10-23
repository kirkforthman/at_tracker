# P0 — Environment & spikes

**Status: complete (2026-10-23).** All exit criteria met.

Goal: a machine where every external source has been probed, the ingest filter exists and is
tested, and the chat model answers a tool call from inside a GPU container. No services yet.

## Steps
| # | Step | Who | Status |
|---|---|---|---|
| 1 | Ingest filter + airline allowlist + unit tests (`ingest/at_ingest/filter.py`) | Claude | done |
| 2 | OpenSky client from `collector/testing.py` → `ingest/at_ingest/opensky.py` (creds from env) | Claude | done |
| 3 | Probe script (real responses to gitignored `ingest/recordings/`); synthetic OpenSky/adsbdb fixtures with ground truth; FAA/METAR public-domain samples; OurAirports shape | Claude | done |
| 4 | CLAUDE.md, `.env.example`, CI (ruff + pytest), ADRs 0001–0002, worklog | Claude | done |
| 5 | Docker Engine + Compose + NVIDIA toolkit (`scripts/setup-wsl-docker.sh`) | User (sudo) | done: GPU visible in containers |
| 6 | WSL memory: confirm RAM, set `memory=24GB` in `%UserProfile%\.wslconfig`, `wsl --shutdown` | User (Windows) | done: 31.8 GB installed, WSL sees 23 GB |
| 7 | OpenSky API client → `.env`; `probe opensky --polls 2` to confirm credits per call | User + Claude | done: 4 credits/call (3,840/day at 90 s) |
| 8 | llama.cpp CUDA container, gpt-oss-20b, tune `--n-cpu-moe`; `scripts/llm_smoke_test.py` | Claude | done: tool call passed, 10.5 GB VRAM at `--n-cpu-moe 6` |
| 9 | Record tokens/s baseline; update PLANNING.md | Claude | done: ~76 tok/s generation, ~185 tok/s prompt |
| 10 | Public GitHub repo; real fixtures replaced by synthetic ones before the first push | User + Claude | done: github.com/kirkforthman/at_tracker |
| 11 | CI green on GitHub; actions moved to Node 24 releases | Claude | done |
| 12 | Branch protection on `main`: PR required, `ingest` check required, applies to admins, linear history | Claude | done |
| 13 | Close-out: pin known-good versions (ADR 0003), Dependabot, allowlist adds KAP + JSX | Claude | done |

## Exit criteria
- ✅ `docker run --rm --gpus all ubuntu nvidia-smi` shows the GPU.
- ✅ `llm_smoke_test.py` passes against `localhost:8081`.
- ✅ Authenticated credit cost per CONUS call confirmed.
- ✅ Synthetic fixtures committed (no real aircraft data in history); tests and lint green in CI.

## Carried into P1
- Run the LLM from `compose.yaml` with the pinned image and model revision from ADR 0003.
- Pin Postgres and Python base images (tag + digest) when they are added.

