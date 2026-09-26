"""Streaming download with progress + resume + cancel + optional sha512 verification."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

import httpx

ProgressCb = Callable[[int, int], None]  # downloaded, total
CancelCb = Callable[[], bool]


class DownloadCancelled(Exception):
    pass


def download(url: str, dest: Path, progress: ProgressCb | None = None,
             client: httpx.Client | None = None, resume: bool = True,
             is_cancelled: CancelCb | None = None) -> Path:
    """Скачивание с докачкой (Range) и проверкой отмены каждый чанк.

    Если dest уже частично скачан — продолжает с места (сервер должен вернуть 206).
    Если сервер Range не поддерживает (200) — начинает заново.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    own = client is None
    c = client or httpx.Client(headers={"User-Agent": "proton-downloader/0.1"},
                               timeout=60, follow_redirects=True)
    try:
        done = 0
        mode = "wb"
        headers: dict[str, str] = {}
        if resume and dest.exists() and dest.stat().st_size > 0:
            done = dest.stat().st_size
            headers["Range"] = f"bytes={done}-"
            mode = "ab"
        with c.stream("GET", url, headers=headers) as r:
            if r.status_code == 416:  # уже скачан целиком
                total = done
                if progress:
                    progress(done, total)
                return dest
            if r.status_code == 206:
                content_range = r.headers.get("content-range", "")
                # "bytes 12345-99999/100000" -> total
                try:
                    total = int(content_range.rsplit("/", 1)[1])
                except Exception:
                    total = done + int(r.headers.get("content-length", 0))
            elif r.status_code == 200 and mode == "ab":
                # сервер проигнорировал Range — качаем заново
                done = 0
                mode = "wb"
                total = int(r.headers.get("content-length", 0))
            else:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
            with open(dest, mode) as f:
                for chunk in r.iter_bytes(chunk_size=1024 * 256):
                    if is_cancelled and is_cancelled():
                        raise DownloadCancelled("Загрузка отменена")
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
