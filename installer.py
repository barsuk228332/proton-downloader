"""Install / list / remove Proton builds in compatibilitytools.d."""
from __future__ import annotations

import shutil
import tarfile
from pathlib import Path
from typing import Callable

ProgressCb = Callable[[int, int], None]
CancelCb = Callable[[], bool]


class InstallCancelled(Exception):
    pass


def candidate_install_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / ".steam/root/compatibilitytools.d",
        home / ".local/share/Steam/compatibilitytools.d",
        home / ".var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d",  # flatpak
        home / ".steam/steam/compatibilitytools.d",
    ]


INSTALL_TARGETS: dict[str, dict] = {
    "steam": {
        "label": "Steam",
        "hint": "compatibilitytools.d — выбор в настройках Steam → Совместимость",
        "candidates": lambda home: [
            home / ".steam/root/compatibilitytools.d",
            home / ".local/share/Steam/compatibilitytools.d",
            home / ".var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d",
            home / ".steam/steam/compatibilitytools.d",
        ],
    },
    "lutris-wine": {
        "label": "Lutris (Wine)",
        "hint": "раннеры Wine — выбор в игре → Configure → Runner options",
        "candidates": lambda home: [
            home / ".local/share/lutris/runners/wine",
            home / ".var/app/net.lutris.Lutris/data/lutris/runners/wine",  # flatpak
        ],
    },
    "lutris-proton": {
        "label": "Lutris (Proton)",
        "hint": "раннеры Proton (Lutris 5.18+) — Preferences → Runners",
        "candidates": lambda home: [
            home / ".local/share/lutris/runners/proton",
            home / ".var/app/net.lutris.Lutris/data/lutris/runners/proton",  # flatpak
        ],
    },
    "bottles": {
        "label": "Bottles",
        "hint": "раннеры — выбор в Preferences → Runners",
        "candidates": lambda home: [
            home / ".local/share/bottles/runners",
            home / ".var/app/com.usebottles.bottles/data/bottles/runners",  # flatpak
        ],
    },
}


def target_ids() -> list[str]:
    return list(INSTALL_TARGETS.keys())


def target_label(tid: str) -> str:
    return INSTALL_TARGETS.get(tid, {}).get("label", tid)


def candidate_dirs_for_target(tid: str) -> list[Path]:
    home = Path.home()
    cfg = INSTALL_TARGETS.get(tid)
    if cfg is None:
        raise ValueError(f"Неизвестная цель: {tid} ({', '.join(target_ids())})")
    return [p for p in cfg["candidates"](home)]


def default_dir_for_target(tid: str) -> Path:
    """Первая существующая папка цели, иначе первая из кандидатов (без создания)."""
    for p in candidate_dirs_for_target(tid):
        if p.exists():
            return p
    return candidate_dirs_for_target(tid)[0]


def target_hint(tid: str) -> str:
    return INSTALL_TARGETS.get(tid, {}).get("hint", "")


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


def extract_archive(archive: Path, install_dir: Path,
                    progress: ProgressCb | None = None,
                    is_cancelled: CancelCb | None = None) -> Path:
    """Распаковка с прогрессом по файлам (для GUI)."""
    install_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as tf:
        members = tf.getmembers()
        total = len(members) or 1
        try:
            filt = "data"
            tf.extractall(install_dir, filter=filt)
            if progress:
                progress(total, total)
            top = members[0].name.split("/")[0] if members else dir_name_for_archive(archive)
        except TypeError:
            # старый Python без filter= — извлекаем по одному для прогресса
            for i, m in enumerate(members, 1):
                if is_cancelled and is_cancelled():
                    raise InstallCancelled("Распаковка отменена")
                tf.extract(m, install_dir)
                if progress and (i % 25 == 0 or i == total):
                    progress(i, total)
            top = members[0].name.split("/")[0] if members else dir_name_for_archive(archive)
        except Exception:
            # filter="data" может запретить часть путей — fallback на поэлементную
            with tarfile.open(archive, "r:*") as tf2:
                members2 = tf2.getmembers()
                total2 = len(members2) or 1
                for i, m in enumerate(members2, 1):
                    if is_cancelled and is_cancelled():
                        raise InstallCancelled("Распаковка отменена")
                    try:
                        tf2.extract(m, install_dir)
                    except Exception:
                        continue
                    if progress and (i % 25 == 0 or i == total2):
                        progress(i, total2)
            top = members2[0].name.split("/")[0] if members2 else dir_name_for_archive(archive)
    target = install_dir / top
    return target if target.exists() else install_dir / dir_name_for_archive(archive)


def cleanup_archive(archive: Path) -> None:
    try:
        if archive.is_file():
            archive.unlink()
    except Exception as e:
        print(f"[warn] cleanup {archive}: {e}")


def list_installed(install_dir: Path) -> list[str]:
    if not install_dir.exists():
        return []
    return sorted(p.name for p in install_dir.iterdir() if p.is_dir())


def list_installed_by_mtime(install_dir: Path) -> list[tuple[str, float]]:
    """[(name, mtime)] от старых к новым."""
    if not install_dir.exists():
        return []
    items = [(p.name, p.stat().st_mtime) for p in install_dir.iterdir() if p.is_dir()]
    items.sort(key=lambda t: t[1])
    return items


def prune_old_builds(install_dir: Path, keep_n: int) -> list[str]:
    """Оставить N самых новых сборок, остальные удалить. Возвращает удалённые."""
    if keep_n <= 0:
        return []
    items = list_installed_by_mtime(install_dir)
    if len(items) <= keep_n:
        return []
    doomed = [name for name, _mt in items[: len(items) - keep_n]]
    for name in doomed:
        try:
            remove_build(install_dir, name)
        except Exception as e:
            print(f"[warn] prune {name}: {e}")
    return doomed


def dir_size(path: Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file() and not p.is_symlink():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def installed_total_size(install_dir: Path) -> int:
    if not install_dir.exists():
        return 0
    return sum(dir_size(p) for p in install_dir.iterdir() if p.is_dir())


def remove_build(install_dir: Path, name: str) -> None:
    target = install_dir / name
    if target.is_dir() and target.parent == install_dir:
        shutil.rmtree(target)
