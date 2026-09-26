"""Entry point: python main.py [--cli-list | --cli-install TAG | --cli-install-url URL | --cli-prune]."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def cli_list():
    from fetcher import fetch_all
    try:
        data = fetch_all(10)
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    for src, rels in data.items():
        print(f"== {src} ({len(rels)}) ==")
        for r in rels[:10]:
            print(f"  {r.tag}  {r.size // 1024 // 1024}MB  {r.url}")


def _install_release(hit, dest: str | None, delete_archive: bool | None = None):
    from downloader import download, fetch_expected_sha512, verify_sha512
    from installer import cleanup_archive, default_install_dir, extract_archive, prune_old_builds
    from settings import load_settings
    s = load_settings()
    if delete_archive is None:
        delete_archive = bool(s.get("delete_archive_after_install", True))
    keep_n = int(s.get("keep_n", 0))
    install_dir = Path(dest).expanduser() if dest else default_install_dir()
    tmp = Path(tempfile.gettempdir()) / "proton-downloader" / hit.url.split("/")[-1].split("?")[0]
    print(f"Скачивание {hit.url} ... (докачка включена)")

    def prog(d, t):
        if t:
            print(f"\r{d / 1024 / 1024:.0f}/{t / 1024 / 1024:.0f} MB", end="")

    try:
        download(hit.url, tmp, progress=prog)
    except KeyboardInterrupt:
        print("\nПрервано (частичный файл сохранён — повтор продолжит).")
        sys.exit(130)
    print()
    if hit.checksum_url:
        exp = fetch_expected_sha512(hit.checksum_url)
        if exp:
            print("Проверка SHA512...", "OK" if verify_sha512(tmp, exp) else "FAIL")
    target = extract_archive(tmp, install_dir)
    print(f"Установлено в {target}. Перезапустите Steam.")
    if delete_archive:
        cleanup_archive(tmp)
        print("Архив удалён.")
    if keep_n > 0:
        pruned = prune_old_builds(install_dir, keep_n)
        if pruned:
            print(f"Удалено старых сборок ({len(pruned)}): {', '.join(pruned)}")


def cli_install(tag: str, dest: str | None):
    from fetcher import fetch_all
    data = fetch_all(30)
    all_rels = [r for v in data.values() for r in v]
    hit = next((r for r in all_rels if r.tag == tag), None)
    if not hit:
        print(f"Тег {tag} не найден. Примеры:")
        for r in all_rels[:5]:
            print(" ", r.tag)
        sys.exit(1)
    _install_release(hit, dest)


def cli_install_url(url: str, dest: str | None):
    from sources import Release
    fname = url.split("/")[-1].split("?")[0]
    if not fname.endswith((".tar.gz", ".tgz", ".tar.xz", ".tar.bz2")):
        print("Нужна ссылка на архив .tar.gz / .tar.xz")
        sys.exit(1)
    tag = fname
    for suffix in (".tar.gz", ".tgz", ".tar.xz", ".tar.bz2"):
        if tag.endswith(suffix):
            tag = tag[: -len(suffix)]
            break
    hit = Release(source="URL", tag=tag, name=tag, url=url, size=0,
                  checksum_url=None, published_at="", body="")
    _install_release(hit, dest)


def cli_prune(dest: str | None, keep: str | None = None):
    from installer import default_install_dir, list_installed, prune_old_builds
    from settings import load_settings
    install_dir = Path(dest).expanduser() if dest else default_install_dir()
    n = int(keep) if keep else int(load_settings().get("keep_n", 0))
    if n <= 0:
        print("Укажите N: --cli-prune [dir] <N> или задайте keep_n в настройках")
        sys.exit(1)
    names = list_installed(install_dir)
    print(f"Сборок: {len(names)}, лимит: {n}")
    pruned = prune_old_builds(install_dir, n)
    print(f"Удалено: {pruned}" if pruned else "Чистить нечего.")


def print_help():
    print("Использование:")
    print("  main.py [--cli-list | --cli-install TAG [DIR] | --cli-install-url URL [DIR] | --cli-prune [DIR] [N]]")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--cli-list":
        cli_list()
    elif len(sys.argv) > 2 and sys.argv[1] == "--cli-install":
        cli_install(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif len(sys.argv) > 2 and sys.argv[1] == "--cli-install-url":
        cli_install_url(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif len(sys.argv) > 1 and sys.argv[1] == "--cli-prune":
        rest = sys.argv[2:]
        dest = rest[0] if rest and not rest[0].isdigit() else None
        keep = next((a for a in rest if a.isdigit()), None)
        if dest is None and keep is None and rest:
            pass
        cli_prune(dest, keep)
    elif len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print_help()
    else:
        from gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
