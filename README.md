# 🎮 Proton Downloader

Удобный загрузчик кастомных сборок **Proton** для Linux — в один клик, без ручного скачивания архивов с GitHub.

Выбираете версию → нажимаете «Установить» → перезапускаете Steam → играете. 🍷

---

## ✨ Возможности

- 📦 **3 источника** в одном окне: Proton-GE, Proton-CachyOS, DWProton
- 🔍 Поиск по версии и сортировка (новые / старые / по размеру)
- 🏷️ Бейджи **Latest** (свежайший релиз) и **Installed** (уже установлен)
- 📥 Скачивание с прогрессом и проверкой контрольной суммы **SHA512**
- 📁 Установка в папку Steam или в любой свой путь
- 🗑️ Удаление установленных сборок прямо из интерфейса
- 💻 Есть CLI-режим без GUI

## 📦 Источники сборок

| Источник | Репозиторий | Файлы |
|----------|-------------|-------|
| **Proton-GE** | [GloriousEggroll/proton-ge-custom](https://github.com/GloriousEggroll/proton-ge-custom) | `GE-Proton*-x86_64.tar.gz` |
| **Proton-CachyOS** | [CachyOS/proton-cachyos](https://github.com/CachyOS/proton-cachyos) | `proton-cachyos-*-x86_64.tar.xz` |
| **DWProton** | [dawn-winery/dwproton](https://dawn.wine/dawn-winery/dwproton) | `dwproton-*-x86_64.tar.xz` |

Архитектура выбирается автоматически (`x86_64` / `aarch64`).
Для CachyOS по умолчанию ставится обычный `x86_64` — так рекомендует сам мейнтейнер.

---

## 🚀 Быстрый старт (готовый бинарник)

Вы собрали программу через PyInstaller — запуск без установки Python:

```bash
cd dist/proton-downloader
./proton-downloader
```

> 📌 Папка `dist/proton-downloader/` должна лежать целиком — бинарник
> использует файлы из `_internal/` рядом с ним.

Чтобы запускать из любого места, создайте ярлык или symlink:

```bash
ln -s ~/proton-downloader/dist/proton-downloader/proton-downloader ~/.local/bin/proton-downloader
proton-downloader
```

## 🐍 Запуск из исходников

Требуется Python 3.10+.

```bash
# 1. Клонируйте / откройте папку проекта
cd proton-downloader

# 2. Создайте виртуальное окружение и поставьте зависимости
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Запустите
.venv/bin/python main.py
```

Зависимости всего две: `PySide6` (интерфейс) и `httpx` (скачивание).

## 🖥️ Как пользоваться

1. **Выберите источник** в сайдбаре слева (или «Все»).
2. **Найдите версию** через поиск, свежайшие помечены бейджем `Latest`.
3. Проверьте **папку установки** внизу сайдбара (определяется сама).
4. Нажмите **«Установить»** на карточке и дождитесь распаковки.
5. **Перезапустите Steam** — новая сборка появится в
   `Настройки Steam → Совместимость` и в свойствах игры.

Установленные версии помечены бейджем `Installed`, удалить можно
кнопкой **«Удалить»** на карточке.

## ⌨️ CLI-режим (без окна)

```bash
# список доступных версий
.venv/bin/python main.py --cli-list

# установить конкретную версию в стандартную папку Steam
.venv/bin/python main.py --cli-install GE-Proton11-7

# установить в свою папку
.venv/bin/python main.py --cli-install GE-Proton11-7 ~/my-protons
```

## 📁 Куда ставится

Программа ищет первую существующую папку из списка:

- `~/.steam/root/compatibilitytools.d`
- `~/.local/share/Steam/compatibilitytools.d`
- `~/.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d` (Flatpak)
- `~/.steam/steam/compatibilitytools.d`

Если ни одной нет — создаёт первую. В интерфейсе путь можно сменить вручную.

## ❓ Частые вопросы

**Steam не видит новый Proton.**
Перезапустите клиент Steam полностью (выход, не сворачивание в трей).

**Ошибка 403 / rate limit exceeded.**
GitHub без авторизации разрешает ~60 запросов к API в час. Подождите час —
DWProton (Forgejo) при этом продолжает работать.

**Сколько весит скачивание?**
Один Proton — примерно 300–550 МБ.

**Нужно ли что-то настраивать для Flatpak-Steam?**
Нет, путь Flatpak определяется автоматически.

## 🗂️ Структура проекта

```
proton-downloader/
├── main.py            # точка входа (GUI + CLI)
├── gui.py             # главное окно: сайдбар + карточки
├── widgets.py         # виджет карточки релиза
├── fetcher.py         # загрузка списков релизов (GitHub / Forgejo)
├── sources.py         # модель Release + выбор архива под архитектуру
├── downloader.py      # скачивание с прогрессом + проверка SHA512
├── installer.py       # распаковка в compatibilitytools.d, удаление
├── requirements.txt
└── dist/              # готовая сборка PyInstaller
```

## 📄 Лицензия

См. файл [LICENSE](LICENSE).
