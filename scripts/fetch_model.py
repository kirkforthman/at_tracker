"""Put the pinned model file at MODEL_PATH and verify its SHA-256 (docs/adr/0003).

Runs as the one-shot `llm-model` Compose service before `llm` starts:
  1. MODEL_PATH exists with the right hash -> done.
  2. A file with the right hash exists elsewhere in the models volume (e.g. the
     llama.cpp -hf cache from P0) -> hard-link it, no download.
  3. Otherwise download MODEL_URL (a pinned Hugging Face revision) and verify.

Standard library only.
"""
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

URL = os.environ["MODEL_URL"]
SHA256 = os.environ["MODEL_SHA256"].lower()
PATH = Path(os.environ["MODEL_PATH"])
CHUNK = 8 << 20


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(CHUNK):
            h.update(b)
    return h.hexdigest()


def find_existing(root, size):
    for p in root.rglob("*.gguf"):
        real = p.resolve()
        if real != PATH.resolve() and real.is_file() and real.stat().st_size == size:
            yield real


def download():
    tmp = PATH.with_suffix(".part")
    h = hashlib.sha256()
    with urllib.request.urlopen(URL, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done, step = 0, 0
        while b := r.read(CHUNK):
            f.write(b)
            h.update(b)
            done += len(b)
            if total and done * 20 // total > step:
                step = done * 20 // total
                print(f"  {done * 100 // total}%", flush=True)
    if h.hexdigest() != SHA256:
        tmp.unlink()
        sys.exit(f"downloaded file hash {h.hexdigest()} != expected {SHA256}")
    tmp.rename(PATH)


def main():
    PATH.parent.mkdir(parents=True, exist_ok=True)
    if PATH.exists():
        print(f"verifying {PATH} ...", flush=True)
        if sha256(PATH) == SHA256:
            print("ok: model present and verified")
            return
        print("hash mismatch: replacing")
        PATH.unlink()
    with urllib.request.urlopen(urllib.request.Request(URL, method="HEAD"), timeout=60) as r:
        size = int(r.headers["Content-Length"])
    for candidate in find_existing(PATH.parent, size):
        print(f"checking existing {candidate} ...", flush=True)
        if sha256(candidate) == SHA256:
            os.link(candidate, PATH)
            print("ok: linked existing verified copy (no download)")
            return
    print(f"downloading {URL}", flush=True)
    download()
    print("ok: downloaded and verified")


if __name__ == "__main__":
    main()
