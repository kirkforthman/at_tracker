# 0001 — Docker Engine + Compose, portable across OSes

Date: 2026-10-23 · Status: accepted

## Context
The finished project should deploy on any OS, limited only by available compute. Development happens
on Windows 11 + WSL2 Ubuntu with an RTX 4070 Ti (12 GB).

## Decision
- Package every service as an OCI image and run them with one `compose.yaml`.
- Develop on **Docker Engine installed inside WSL** (not Docker Desktop), with the NVIDIA Container
  Toolkit for GPU access. Linux servers, cloud VMs and CI runners run Docker Engine, so dev matches
  deployment. Docker Desktop stays a fallback.
- The LLM is the only hardware-bound component. It sits behind `LLM_BASE_URL` with Compose profiles:
  `gpu-nvidia` (llama.cpp CUDA), `cpu` (llama.cpp CPU, smaller model), or no profile with an external
  URL (native llama.cpp on macOS/Metal, another machine, or a hosted OpenAI-compatible API).
- Multi-arch images (amd64 + arm64), named volumes only, config via `.env`.

## Consequences
- macOS hosts can't give containers GPU access, so they use an external `LLM_BASE_URL`.
- The app must keep working (map, focus box) when the LLM is unreachable.
