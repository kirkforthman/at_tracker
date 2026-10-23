# 0003 — Pin known-good versions

Date: 2026-10-23 · Status: accepted

## Context
The project should deploy reproducibly on other hardware. Floating versions (`latest`, `server-cuda`,
`flask>=3.0`, `actions/checkout@v4`) can change underneath us without any change in this repo, as
seen with the llama.cpp image: its `server-cuda` tag points to a new build every day.

## Decision
Pin every version that is (a) known good, meaning tested in this project, and (b) cheap to pin.
Use the most exact form available:

| Kind | How it's pinned | Where |
|---|---|---|
| Python packages | `==` for every package, including transitive dependencies | `ingest/requirements.txt`, `dashboard/requirements.txt` (`pyproject.toml` keeps ranges for compatibility) |
| Python interpreter | Exact patch version | CI `python-version`; container base images from P1 |
| GitHub Actions | Commit SHA, with the version in a comment | `.github/workflows/*.yml` |
| Container images | Version tag **and** digest (`image:tag@sha256:…`) | `compose.yaml` from P1 |
| Model weights | Hugging Face revision in the download URL, plus a SHA-256 check | `compose.yaml` / LLM service from P1 |

Not pinned, because the tradeoff is poor: host packages installed with apt (Docker Engine, NVIDIA
toolkit, the GPU driver). Pinning them would block security updates. They are recorded below as
tested versions instead.

**Keeping pins fresh:** Dependabot (`.github/dependabot.yml`) proposes monthly bump PRs for Actions and
pip. A bump merges only if CI passes, because `main` is protected. New versions are adopted
deliberately rather than at random.

## Known-good versions (2026-10-23)

| Component | Version |
|---|---|
| Python | 3.14.4 |
| llama.cpp server | `ghcr.io/ggml-org/llama.cpp:server-cuda-b11804@sha256:490d8cd8000203a3ab8fdfce14ef931e2aa85affd4dd4447bcc75f299f00fd9a` (build 11804, commit `c7fc50941`) |
| Model | `ggml-org/gpt-oss-20b-GGUF` revision `15dcfc7e7c608c6161507211ed43c5b590801b4b`, `gpt-oss-20b-MXFP4.gguf`, SHA-256 `27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901` |
| actions/checkout | v7.0.1 (`3d3c42e5aac5ba805825da76410c181273ba90b1`) |
| actions/setup-python | v7.0.0 (`5fda3b95a4ea91299a34e894583c3862153e4b97`) |
| Docker Engine / Compose (host, not pinned) | 29.9.2 / 5.6.1 |
| NVIDIA Container Toolkit (host, not pinned) | 1.20.1 |
| NVIDIA driver (Windows host, not pinned) | 610.88 |

## Consequences
- Rebuilding on new hardware gets the same software that was tested here.
- Security fixes arrive through Dependabot PRs instead of silently; someone has to merge them.
- Changing a pinned version is an explicit commit, which makes it easy to trace when behavior changed.
