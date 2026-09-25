# Proton Downloader

GUI-загрузчик Proton для Linux (Python + PySide6).

Источники:
- **Proton-GE** — `GloriousEggroll/proton-ge-custom` (GitHub Releases, `GE-Proton*-x86_64.tar.gz`)
- **Proton-CachyOS** — `CachyOS/proton-cachyos` (GitHub Releases, `proton-cachyos-*-x86_64.tar.xz`)
- **DWProton** — `dawn-winery/dwproton` (Forgejo API `dawn.wine`, `dwproton-*-x86_64.tar.xz`)

## Установка

```bash
pip install -r requirements.txt
python main.py
```

## CLI (без GUI)

```bash
python main.py --cli-list
python main.py --cli-install GE-Proton11-7
python main.py --cli-install GE-Proton11-7 ~/custom/path
```

## Куда ставится

Автоопределение первого существующего каталога:
- `~/.steam/root/compatibilitytools.d`
- `~/.local/share/Steam/compatibilitytools.d`
- `~/.var/app/com.valvesoftware.Steam/...` (flatpak)
- `~/.steam/steam/compatibilitytools.d`

В GUI путь можно поменять вручную. После установки перезапустите Steam.
