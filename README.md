# 🎮 Proton Downloader

Удобный загрузчик кастомных сборок **Proton** для Linux — в один клик, без ручного скачивания архивов с GitHub.

Выбираете версию → нажимаете «Установить» → перезапускаете Steam → играете. 🍷

---

## ✨ Возможности

- 📦 **6 источников** в одном окне: Proton-GE, Proton-CachyOS, DWProton, Proton-Sarek, Luxtorpeda, Kron4ek-Proton
- 🔍 Поиск по версии и сортировка (новые / старые / по размеру)
- 🏷️ Бейджи **Latest** (свежайший релиз) и **Installed** (уже установлен)
- 📜 Кнопка «Что нового» — changelog релиза прямо в карточке
- 📥 Скачивание с прогрессом, скоростью, ETA, паузой-докачкой (Resume) и кнопкой отмены
- ✅ Проверка контрольной суммы **SHA512** (где публикует автор)
- 📁 Установка в папку Steam, по прямому URL или в любой свой путь
- 🗑️ Удаление установленных сборок, счётчик места, авточистка «держать N последних»
- 🔑 GitHub-токен в настройках против rate-limit + кэш списка при офлайне
- 💻 Есть CLI-режим без GUI

## 📦 Источники сборок

| Источник | Репозиторий | Файлы |
|----------|-------------|-------|
| **Proton-GE** | [GloriousEggroll/proton-ge-custom](https://github.com/GloriousEggroll/proton-ge-custom) | `GE-Proton*-x86_64.tar.gz` |
| **Proton-CachyOS** | [CachyOS/proton-cachyos](https://github.com/CachyOS/proton-cachyos) | `proton-cachyos-*-x86_64.tar.xz` |
| **DWProton** | [dawn-winery/dwproton](https://dawn.wine/dawn-winery/dwproton) | `dwproton-*-x86_64.tar.xz` |
| **Proton-Sarek** | [pythonlover02/Proton-Sarek](https://github.com/pythonlover02/Proton-Sarek) | `Proton-Sarek*.tar.gz` (для старых GPU, без async-варианта) |
| **Luxtorpeda** | [luxtorpeda/luxtorpeda](https://codeberg.org/luxtorpeda/luxtorpeda) | `luxtorpeda-*.tar.xz` (нативные движки) |
| **Kron4ek-Proton** | [Kron4ek/Wine-Builds](https://github.com/Kron4ek/Wine-Builds) | `wine-proton-*-amd64-wow64.tar.xz` (без SHA-проверки) |

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

# установить по прямой ссылке на архив
.venv/bin/python main.py --cli-install-url https://example.com/foo.tar.xz ~/my-protons

# оставить N самых новых сборок, остальные удалить
.venv/bin/python main.py --cli-prune 3
.venv/bin/python main.py --cli-prune ~/my-protons 3
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
├── gui.py             # главное окно: сайдбар + карточки + настройки
├── widgets.py         # виджет карточки релиза (changelog, скорость/ETA)
├── fetcher.py         # загрузка списков релизов (GitHub / Forgejo) + кэш
├── sources.py         # модель Release + выбор архива под архитектуру
├── downloader.py      # скачивание с прогрессом, докачкой, отменой + SHA512
├── installer.py       # распаковка с прогрессом, удаление, авточистка
├── settings.py        # настройки (токен, keep-N) + кэш в ~/.cache
├── requirements.txt
└── dist/              # готовая сборка PyInstaller
```

## 📄 Лицензия

См. файл [LICENSE](LICENSE).
