"""Fetching releases from GitHub and Forgejo (dawn.wine, codeberg)."""
from __future__ import annotations

import httpx

from settings import get_github_token, load_fetch_cache, save_fetch_cache
from sources import (
    Release,
    forgejo_to_releases,
    github_to_releases,
    pick_cachyos_asset,
    pick_dwproton_asset,
    pick_ge_asset,
    pick_generic_tar_gz,
    pick_generic_tar_xz,
    pick_kron4ek_asset,
)

SOURCES = {
    "Proton-GE": {
        "type": "github",
        "repo": "GloriousEggroll/proton-ge-custom",
        "picker": "ge",
    },
    "Proton-CachyOS": {
        "type": "github",
        "repo": "CachyOS/proton-cachyos",
        "picker": "cachyos",
    },
    "DWProton": {
        "type": "forgejo",
        "repo": "dawn-winery/dwproton",
        "api": "https://dawn.wine/api/v1/repos/dawn-winery/dwproton/releases",
        "picker": "dwproton",
    },
    "Proton-Sarek": {
        "type": "github",
        "repo": "pythonlover02/Proton-Sarek",
        "picker": "generic_gz",
    },
    "Luxtorpeda": {
        "type": "forgejo",
        "repo": "luxtorpeda/luxtorpeda",
        "api": "https://codeberg.org/api/v1/repos/luxtorpeda/luxtorpeda/releases",
        "picker": "generic_xz",
    },
    "Kron4ek-Proton": {
        "type": "github",
        "repo": "Kron4ek/Wine-Builds",
        "picker": "kron4ek",
    },
}

PICKERS = {
    "ge": pick_ge_asset,
    "cachyos": pick_cachyos_asset,
    "dwproton": pick_dwproton_asset,
    "generic_gz": pick_generic_tar_gz,
    "generic_xz": pick_generic_tar_xz,
    "kron4ek": pick_kron4ek_asset,
}

BASE_HEADERS = {"User-Agent": "proton-downloader/0.1", "Accept": "application/vnd.github+json"}


def github_headers() -> dict:
    h = dict(BASE_HEADERS)
    tok = get_github_token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def fetch_github(repo: str, limit: int = 20, client: httpx.Client | None = None) -> list[dict]:
    own = client is None
    c = client or httpx.Client(headers=github_headers(), timeout=30, follow_redirects=True)
    try:
        r = c.get(f"https://api.github.com/repos/{repo}/releases", params={"per_page": limit})
        r.raise_for_status()
        return r.json()
    finally:
        if own:
            c.close()


def fetch_forgejo(api_url: str, limit: int = 20, client: httpx.Client | None = None) -> list[dict]:
    own = client is None
    c = client or httpx.Client(headers={"User-Agent": BASE_HEADERS["User-Agent"]}, timeout=30, follow_redirects=True)
    try:
        r = c.get(api_url, params={"limit": limit})
        r.raise_for_status()
        return r.json()
    finally:
        if own:
            c.close()


def _picker_for(name: str):
    return PICKERS.get(SOURCES[name].get("picker", "ge"), pick_ge_asset)


def fetch_source(name: str, limit: int = 20) -> list[Release]:
    cfg = SOURCES[name]
    if cfg["type"] == "github":
        data = fetch_github(cfg["repo"], limit)
        return github_to_releases(name, data, _picker_for(name))
    data = fetch_forgejo(cfg["api"], limit)
    picker = PICKERS.get(cfg.get("picker", "dwproton"), pick_dwproton_asset)
    return forgejo_to_releases(name, data, picker)


def _release_to_dict(r: Release) -> dict:
    return {"source": r.source, "tag": r.tag, "name": r.name, "url": r.url,
            "size": r.size, "checksum_url": r.checksum_url,
            "published_at": r.published_at, "body": r.body}


def _dict_to_release(d: dict) -> Release:
    return Release(source=d.get("source", ""), tag=d.get("tag", ""), name=d.get("name", ""),
                   url=d.get("url", ""), size=d.get("size", 0),
                   checksum_url=d.get("checksum_url"), published_at=d.get("published_at", ""),
                   body=d.get("body", "") or "")


def fetch_all(limit_per_source: int = 20, use_cache_on_error: bool = True) -> dict[str, list[Release]]:
    """При ошибке сети/rate-limit — fallback на кэш (если есть). Успех — перезапись кэша."""
    result: dict[str, list[Release]] = {}
    errors: list[str] = []
    old_cache, _stale = load_fetch_cache(max_age=10**10)
    with httpx.Client(headers=github_headers(), timeout=30, follow_redirects=True) as client:
        for name, cfg in SOURCES.items():
            try:
                if cfg["type"] == "github":
                    data = fetch_github(cfg["repo"], limit_per_source, client)
                    result[name] = github_to_releases(name, data, _picker_for(name))
                else:
                    # forgejo-клиент без github-токена
                    data = fetch_forgejo(cfg["api"], limit_per_source)
                    picker = PICKERS.get(cfg.get("picker", "dwproton"), pick_dwproton_asset)
                    result[name] = forgejo_to_releases(name, data, picker)
                if not result[name]:
                    raise RuntimeError("пустой список релизов")
            except Exception as e:  # keep other sources working
                errors.append(f"{name}: {e}")
                print(f"[warn] {name}: {e}")
                if use_cache_on_error and old_cache and old_cache.get(name):
                    result[name] = [_dict_to_release(d) for d in old_cache[name]]
                    print(f"[info] {name}: показаны кэшированные данные")
                else:
                    result[name] = []
    total = sum(len(v) for v in result.values())
    if total:
        try:
            save_fetch_cache({k: [_release_to_dict(r) for r in v] for k, v in result.items()})
        except Exception as e:
            print(f"[warn] cache: {e}")
    elif use_cache_on_error:
        cached, _stale = load_fetch_cache(max_age=10**10)
        if cached:
            print("[info] showing cached releases (network failed)")
            return {k: [_dict_to_release(d) for d in v] for k, v in cached.items() if k in SOURCES}
    if errors and total == 0:
        raise RuntimeError("; ".join(errors))
    return result


def load_cached_releases() -> dict[str, list[Release]] | None:
    cached, _stale = load_fetch_cache(max_age=10**10)
    if not cached:
        return None
    return {k: [_dict_to_release(d) for d in v] for k, v in cached.items() if k in SOURCES}
