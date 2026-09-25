"""Streaming download with progress + optional sha512 verification."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

import httpx

ProgressCb = Callable[[int, int], None]  # downloaded, total


def download(url: str, dest: Path, progress: ProgressCb | None = None,
             client: httpx.Client | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    own = client is None
    c = client or httpx.Client(headers={"User-Agent": "proton-downloader/0.1"},
                               timeout=60, follow_redirects=True)
    try:
        with c.stream("GET", url) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=1024 * 256):
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
        return dest
    finally:
        if own:
            c.close()


def fetch_expected_sha512(checksum_url: str) -> str | None:
    """Checksum files contain '<hash>  <filename>'. Return hash or None."""
    try:
        r = httpx.get(checksum_url, timeout=30, follow_redirects=True,
                      headers={"User-Agent": "proton-downloader/0.1"})
        r.raise_for_status()
        return r.text.strip().split()[0]
    except Exception as e:
        print(f"[warn] checksum fetch failed: {e}")
        return None


def verify_sha512(path: Path, expected: str) -> bool:
    h = hashlib.sha512()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower() == expected.lower()
