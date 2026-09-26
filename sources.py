"""Unified release model + fetchers for all Proton sources."""
from __future__ import annotations

import platform
from dataclasses import dataclass


@dataclass
class Release:
    source: str
    tag: str
    name: str
    url: str
    size: int
    checksum_url: str | None
    published_at: str
    body: str = ""

    @property
    def display_name(self) -> str:
        return f"[{self.source}] {self.tag}"


def _machine() -> str:
    return platform.machine().lower()


def pick_ge_asset(assets: list[dict]) -> tuple[dict | None, dict | None]:
    """Pick correct GE-Proton tarball for current arch. Returns (archive, checksum).

    Naming history:
    - new: GE-Proton11-7-x86_64.tar.gz + GE-Proton11-7-aarch64.tar.gz
    - transitional (11-1..11-3): GE-Proton11-3.tar.gz (=x86_64) + GE-Proton11-3-aarch64.tar.gz
    - old: GE-Proton10-34.tar.gz (=x86_64 only)
    """
    m = _machine()
    is_arm = m in ("aarch64", "arm64")
    cands = [a for a in assets if a.get("name", "").endswith(".tar.gz")]
    sums = [a for a in assets if a.get("name", "").endswith(".sha512sum")]
    archive = None
    if is_arm:
        for a in cands:
            if "aarch64" in a["name"] or "arm64" in a["name"]:
                archive = a
                break
    else:
        for a in cands:
            if "x86_64" in a["name"]:
                archive = a
                break
        if archive is None:
            # plain name without arch suffix == x86_64 build
            for a in cands:
                n = a["name"]
                if "aarch64" not in n and "arm64" not in n:
                    archive = a
                    break
    if archive is None:
        return None, None
    checksum = None
    # checksum file mirrors archive name: <archive>.sha512sum or <base>.sha512sum
    want = archive["name"] + ".sha512sum"
    alt = archive["name"].replace(".tar.gz", ".sha512sum")
    for s in sums:
        if s["name"] in (want, alt):
            checksum = s
            break
    return archive, checksum


def pick_cachyos_asset(assets: list[dict]) -> tuple[dict | None, dict | None]:
    """Prefer plain x86_64 build (maintainer recommendation), arm64 on arm."""
    m = _machine()
    if m in ("aarch64", "arm64"):
        keys = ("arm64",)
    else:
        keys = ("x86_64.tar.xz",)  # excludes x86_64_v3 on purpose
    archive = checksum = None
    for a in assets:
        n = a.get("name", "")
        if n.endswith(".tar.xz") and all(k in n for k in keys):
            # skip v3 variant when looking for plain x86_64
            if "x86_64.tar.xz" in keys and "_v3" in n:
                continue
            archive = a
            break
    if archive is not None:
        base = archive["name"] + ".sha512sum"  # actually checksum file is <name>.sha512sum? no, separate name
        # checksum asset name == archive name with .sha512sum suffix replaced:
        # e.g. proton-cachyos-...-x86_64.tar.xz -> proton-cachyos-...-x86_64.sha512sum
        want_sum = archive["name"].replace(".tar.xz", ".sha512sum")
        for a in assets:
            if a.get("name") == want_sum:
                checksum = a
                break
    return archive, checksum


def pick_dwproton_asset(assets: list[dict]) -> tuple[dict | None, dict | None]:
    return pick_generic_tar_xz(assets)


def pick_generic_tar_xz(assets: list[dict]) -> tuple[dict | None, dict | None]:
    """First .tar.xz (skip .torrent). Checksum: .sha512sum/.sha512 (append or replace)."""
    archive = checksum = None
    for a in assets:
        n = a.get("name", "")
        if n.endswith(".tar.xz") and not n.endswith(".torrent"):
            archive = a
            break
    if archive is not None:
        cands = (archive["name"] + ".sha512sum", archive["name"] + ".sha512",
                 archive["name"].replace(".tar.xz", ".sha512sum"),
                 archive["name"].replace(".tar.xz", ".sha512"))
        for a in assets:
            if a.get("name") in cands:
                checksum = a
                break
    return archive, checksum


def pick_generic_tar_gz(assets: list[dict]) -> tuple[dict | None, dict | None]:
    """First .tar.gz + matching .sha512sum (for GE-like sources, e.g. Sarek).

    Sarek публикует обычный и async-вариант — предпочитаем обычный.
    """
    cands = [a for a in assets if a.get("name", "").endswith(".tar.gz")]
    archive = None
    for a in cands:
        if "async" not in a["name"].lower():
            archive = a
            break
    if archive is None and cands:
        archive = cands[0]
    checksum = None
    if archive is not None:
        for suffix in (archive["name"] + ".sha512sum",
                       archive["name"].replace(".tar.gz", ".sha512sum")):
            for a in assets:
                if a.get("name") == suffix:
                    checksum = a
                    break
            if checksum is not None:
                break
    return archive, checksum


def pick_kron4ek_asset(assets: list[dict]) -> tuple[dict | None, dict | None]:
    """Kron4ek/Wine-Builds: wine-proton-*-amd64-wow64.tar.xz (amd64 == x86_64).

    Контрольных сумм per-file нет (только общий sha256sums.txt другого формата),
    поэтому checksum всегда None — проверка пропускается.
    """
    m = _machine()
    is_arm = m in ("aarch64", "arm64")
    archive = None
    if is_arm:
        for a in assets:
            n = a.get("name", "")
            ln = n.lower()
            if n.endswith(".tar.xz") and "proton" in ln and ("aarch64" in ln or "arm64" in ln):
                archive = a
                break
    else:
        # предпочесть wow64-сборку, затем обычную amd64 (=x86_64)
        for a in assets:
            n = a.get("name", "")
            ln = n.lower()
            if n.endswith(".tar.xz") and "proton" in ln and "wow64" in ln \
                    and ("amd64" in ln or "x86_64" in ln):
                archive = a
                break
        if archive is None:
            for a in assets:
                n = a.get("name", "")
                ln = n.lower()
                if n.endswith(".tar.xz") and "proton" in ln \
                        and ("amd64" in ln or "x86_64" in ln):
                    archive = a
                    break
    if archive is None:  # fallback: любой proton tar.xz
        for a in assets:
            n = a.get("name", "")
            if n.endswith(".tar.xz") and "proton" in n.lower():
                archive = a
                break
    return archive, None


def github_to_releases(source: str, data: list[dict], picker) -> list[Release]:
    out: list[Release] = []
    for r in data:
        assets = r.get("assets", [])
        archive, checksum = picker(assets)
        if archive is None:
            continue
        out.append(
            Release(
                source=source,
                tag=r.get("tag_name", ""),
                name=r.get("name") or r.get("tag_name", ""),
                url=archive.get("browser_download_url", ""),
                size=archive.get("size", 0),
                checksum_url=(checksum or {}).get("browser_download_url"),
                published_at=r.get("published_at", ""),
                body=r.get("body", "") or "",
            )
        )
    return out


def forgejo_to_releases(source: str, data: list[dict], picker=None) -> list[Release]:
    pick = picker or pick_dwproton_asset
    out: list[Release] = []
    for r in data:
        assets = r.get("assets", [])
        archive, checksum = pick(
            [{"name": a.get("name", ""), "size": a.get("size", 0),
              "browser_download_url": a.get("browser_download_url", "")} for a in assets]
        )
        if archive is None:
            continue
        out.append(
            Release(
                source=source,
                tag=r.get("tag_name", ""),
                name=r.get("name") or r.get("tag_name", ""),
                url=archive.get("browser_download_url", ""),
                size=archive.get("size", 0),
                checksum_url=(checksum or {}).get("browser_download_url"),
                published_at=r.get("created_at", ""),
                body=r.get("body", "") or "",
            )
        )
    return out
