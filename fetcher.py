"""Fetching releases from GitHub and Forgejo (dawn.wine)."""
from __future__ import annotations

import httpx

from sources import (
    Release,
    forgejo_to_releases,
    github_to_releases,
    pick_cachyos_asset,
    pick_ge_asset,
)

SOURCES = {
    "Proton-GE": {
        "type": "github",
        "repo": "GloriousEggroll/proton-ge-custom",
    },
    "Proton-CachyOS": {
        "type": "github",
        "repo": "CachyOS/proton-cachyos",
    },
    "DWProton": {
        "type": "forgejo",
        "repo": "dawn-winery/dwproton",
        "api": "https://dawn.wine/api/v1/repos/dawn-winery/dwproton/releases",
    },
}

HEADERS = {"User-Agent": "proton-downloader/0.1", "Accept": "application/vnd.github+json"}


def fetch_github(repo: str, limit: int = 20, client: httpx.Client | None = None) -> list[dict]:
    own = client is None
    c = client or httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)
    try:
        r = c.get(f"https://api.github.com/repos/{repo}/releases", params={"per_page": limit})
        r.raise_for_status()
        return r.json()
    finally:
        if own:
            c.close()


def fetch_forgejo(api_url: str, limit: int = 20, client: httpx.Client | None = None) -> list[dict]:
    own = client is None
    c = client or httpx.Client(headers={"User-Agent": HEADERS["User-Agent"]}, timeout=30, follow_redirects=True)
    try:
        r = c.get(api_url, params={"limit": limit})
        r.raise_for_status()
        return r.json()
    finally:
        if own:
            c.close()


def fetch_source(name: str, limit: int = 20) -> list[Release]:
    cfg = SOURCES[name]
    if cfg["type"] == "github":
        data = fetch_github(cfg["repo"], limit)
        picker = pick_ge_asset if name == "Proton-GE" else pick_cachyos_asset
        return github_to_releases(name, data, picker)
    data = fetch_forgejo(cfg["api"], limit)
    return forgejo_to_releases(name, data)


def fetch_all(limit_per_source: int = 20) -> dict[str, list[Release]]:
    result: dict[str, list[Release]] = {}
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for name, cfg in SOURCES.items():
            try:
                if cfg["type"] == "github":
                    data = fetch_github(cfg["repo"], limit_per_source, client)
                    picker = pick_ge_asset if name == "Proton-GE" else pick_cachyos_asset
                    result[name] = github_to_releases(name, data, picker)
                else:
                    data = fetch_forgejo(cfg["api"], limit_per_source, client)
                    result[name] = forgejo_to_releases(name, data)
            except Exception as e:  # keep other sources working
                result[name] = []
                print(f"[warn] {name}: {e}")
    return result
