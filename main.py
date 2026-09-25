"""Entry point: python main.py [--cli-list | --cli-install TAG]."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def cli_list():
    from fetcher import fetch_all
    data = fetch_all(10)
    for src, rels in data.items():
        print(f"== {src} ({len(rels)}) ==")
        for r in rels[:10]:
            print(f"  {r.tag}  {r.size // 1024 // 1024}MB  {r.url}")


def cli_install(tag: str, dest: str | None):
    from downloader import download, fetch_expected_sha512, verify_sha512
    from fetcher import fetch_all
    from installer import default_install_dir, extract_archive
    data = fetch_all(30)
    all_rels = [r for v in data.values() for r in v]
    hit = next((r for r in all_rels if r.tag == tag), None)
    if not hit:
        print(f"Тег {tag} не найден. Примеры:")
        for r in all_rels[:5]:
            print(" ", r.tag)
        sys.exit(1)
    install_dir = Path(dest).expanduser() if dest else default_install_dir()
    tmp = Path(tempfile.gettempdir()) / "proton-downloader" / hit.url.split("/")[-1]
    print(f"Скачивание {hit.url} ...")

    def prog(d, t):
        if t:
            print(f"\r{d / 1024 / 1024:.0f}/{t / 1024 / 1024:.0f} MB", end="")

    download(hit.url, tmp, progress=prog)
    print()
    if hit.checksum_url:
        exp = fetch_expected_sha512(hit.checksum_url)
        if exp:
            print("Проверка SHA512...", "OK" if verify_sha512(tmp, exp) else "FAIL")
    target = extract_archive(tmp, install_dir)
    print(f"Установлено в {target}. Перезапустите Steam.")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--cli-list":
        cli_list()
    elif len(sys.argv) > 2 and sys.argv[1] == "--cli-install":
        cli_install(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        from gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
