"""Install / list / remove Proton builds in compatibilitytools.d."""
from __future__ import annotations

import shutil
import tarfile
from pathlib import Path


def candidate_install_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / ".steam/root/compatibilitytools.d",
        home / ".local/share/Steam/compatibilitytools.d",
        home / ".var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d",  # flatpak
        home / ".steam/steam/compatibilitytools.d",
    ]


def default_install_dir() -> Path:
    for p in candidate_install_dirs():
        if p.exists():
            return p
    d = candidate_install_dirs()[0]
    d.mkdir(parents=True, exist_ok=True)
    return d


def dir_name_for_archive(archive: Path) -> str:
    """GE-Proton11-7-x86_64.tar.gz -> GE-Proton11-7 ; foo.tar.xz -> foo."""
    n = archive.name
    for suffix in (".tar.gz", ".tgz", ".tar.xz", ".tar.bz2"):
        if n.endswith(suffix):
            n = n[: -len(suffix)]
            break
    # CachyOS/dwproton archives already contain arch suffix which IS the dir name
    # used by Steam (e.g. proton-cachyos-...-x86_64). Keep as is.
    return n


def extract_archive(archive: Path, install_dir: Path) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as tf:
        # safety: prevent path traversal (tarfile filter where available)
        try:
            tf.extractall(install_dir, filter="data")
        except TypeError:
            tf.extractall(install_dir)
    # archive usually contains a single top-level dir; return it
    # derive from first member
    with tarfile.open(archive, "r:*") as tf:
        top = tf.getnames()[0].split("/")[0] if tf.getnames() else dir_name_for_archive(archive)
    target = install_dir / top
    return target if target.exists() else install_dir / dir_name_for_archive(archive)


def list_installed(install_dir: Path) -> list[str]:
    if not install_dir.exists():
        return []
    return sorted(p.name for p in install_dir.iterdir() if p.is_dir())


def remove_build(install_dir: Path, name: str) -> None:
    target = install_dir / name
    if target.is_dir() and target.parent == install_dir:
        shutil.rmtree(target)
