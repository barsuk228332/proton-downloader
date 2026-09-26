"""Persistent settings + fetch cache (token, keep-N, autoclean)."""
from __future__ import annotations

import json
import time
from pathlib import Path


def config_dir() -> Path:
    d = Path.home() / ".config" / "proton-downloader"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    d = Path.home() / ".cache" / "proton-downloader"
    d.mkdir(parents=True, exist_ok=True)
    return d


def settings_path() -> Path:
    return config_dir() / "settings.json"


def cache_path() -> Path:
    return cache_dir() / "releases.json"


DEFAULTS = {
    "github_token": "",
    "keep_n": 0,  # 0 = не чистить автоматически
    "delete_archive_after_install": True,
    "auto_prune": False,
    "target": "steam",  # steam | lutris-wine | lutris-proton | bottles
}

CACHE_TTL = 3600  # 1 час


def load_settings() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        out = dict(DEFAULTS)
        out.update({k: v for k, v in data.items() if k in DEFAULTS})
        return out
    except Exception:
        return dict(DEFAULTS)


def save_settings(s: dict) -> None:
    keep = {k: s.get(k, DEFAULTS[k]) for k in DEFAULTS}
    settings_path().write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")


def get_github_token() -> str:
    return (load_settings().get("github_token") or "").strip()


# --- fetch cache ---

def save_fetch_cache(payload: dict[str, list[dict]]) -> None:
    """payload: {source: [release_dict, ...]} — уже сериализуемое."""
    try:
        cache_path().write_text(
            json.dumps({"saved_at": time.time(), "data": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[warn] cache save failed: {e}")


def load_fetch_cache(max_age: int = CACHE_TTL) -> tuple[dict | None, bool]:
    """Returns (data, is_stale). data None если кэша нет."""
    try:
        raw = json.loads(cache_path().read_text(encoding="utf-8"))
        age = time.time() - float(raw.get("saved_at", 0))
        return raw.get("data"), age > max_age
    except Exception:
        return None, True
