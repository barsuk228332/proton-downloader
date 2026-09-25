"""PySide6 GUI: sidebar + cards, system theme, search + badges."""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSplitter, QStatusBar, QVBoxLayout, QWidget,
)

from downloader import download, fetch_expected_sha512, verify_sha512
from fetcher import SOURCES, fetch_all
from installer import default_install_dir, extract_archive, list_installed, remove_build
from sources import Release
from widgets import ReleaseCard

SOURCE_NAMES = ["Все", *SOURCES.keys()]

QSS = """
#Sidebar { font-size: 14px; }
#Sidebar::item { padding: 8px 10px; border-radius: 8px; }
#Sidebar::item:selected { font-weight: bold; }
#ReleaseCard { border: 1px solid palette(mid); border-radius: 10px; }
#CardTitle { font-size: 15px; font-weight: bold; }
#CardMeta { color: palette(placeholder-text); }
#Badge_Latest, #Badge_Installed {
    border-radius: 8px; padding: 2px 10px; font-size: 12px; font-weight: bold;
}
#Badge_Latest { border: 1px solid palette(highlight); color: palette(highlight); }
#Badge_Installed { border: 1px solid palette(mid); }
#Search { padding: 6px 10px; border-radius: 8px; }
"""


class FetchWorker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, limit: int = 20):
        super().__init__()
        self.limit = limit

    def run(self):
        try:
            self.done.emit(fetch_all(self.limit))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class DownloadWorker(QThread):
    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, release: Release, install_dir: Path):
        super().__init__()
        self.release = release
        self.install_dir = install_dir

    def run(self):
        try:
            tmp = Path(tempfile.gettempdir()) / "proton-downloader"
            tmp.mkdir(parents=True, exist_ok=True)
            archive = tmp / self.release.url.split("/")[-1]
            download(self.release.url, archive,
                     progress=lambda d, t: self.progress.emit(d, t))
            if self.release.checksum_url:
                expected = fetch_expected_sha512(self.release.checksum_url)
                if expected and not verify_sha512(archive, expected):
                    self.failed.emit("SHA512 mismatch — файл повреждён")
                    return
            target = extract_archive(archive, self.install_dir)
            self.done.emit(str(target))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


def possible_dir_names(r: Release) -> set[str]:
    """Candidate installed-folder names for a release (lowercased)."""
    out = {r.tag.lower()}
    fname = r.url.split("/")[-1]
    for suffix in (".tar.gz", ".tgz", ".tar.xz", ".tar.bz2"):
        if fname.endswith(suffix):
            fname = fname[: -len(suffix)]
            break
    out.add(fname.lower())
    # GE archives carry arch suffix, installed dir does not: GE-Proton11-7-x86_64 -> GE-Proton11-7
    for arch in ("-x86_64", "-aarch64", "_x86_64", "_aarch64", ".x86_64"):
        if fname.lower().endswith(arch):
            out.add(fname[: -len(arch)].lower())
    return out


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Proton Downloader")
        self.resize(1000, 650)
        self.by_source: dict[str, list[Release]] = {}
        self.latest_tags: set[str] = set()
        self.installed: set[str] = set()  # lowercased dir names
        self.cards: dict[str, ReleaseCard] = {}  # key = source+tag
        self.worker: QThread | None = None
        self.active_card: ReleaseCard | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)

        # top bar: search + sort + refresh
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Поиск по версии…")
        self.search.textChanged.connect(self.rebuild_cards)
        top.addWidget(self.search, 1)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Сначала новые", "Сначала старые", "Сначала большие", "Сначала маленькие"])
        self.sort_combo.currentIndexChanged.connect(self.rebuild_cards)
        top.addWidget(self.sort_combo)
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        root.addLayout(top)

        split = QSplitter(Qt.Horizontal)

        # sidebar
        side_box = QWidget()
        side_layout = QVBoxLayout(side_box)
        side_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.currentRowChanged.connect(self.rebuild_cards)
        side_layout.addWidget(self.sidebar, 1)
        # install dir row (compact, in sidebar bottom)
        side_layout.addWidget(QLabel("Установка в:"))
        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit(str(default_install_dir()))
        self.dir_edit.textChanged.connect(self.reload_installed)
        dir_row.addWidget(self.dir_edit, 1)
        browse = QPushButton("…")
        browse.setFixedWidth(36)
        browse.clicked.connect(self.browse_dir)
        dir_row.addWidget(browse)
        side_layout.addLayout(dir_row)
        split.addWidget(side_box)

        # cards scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards_host = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch(1)
        self.scroll.setWidget(self.cards_host)
        split.addWidget(self.scroll)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([220, 760])
        root.addWidget(split, 1)

        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        # compat for old tests/scripts
        self.source_combo = self.sidebar  # rows map to SOURCE_NAMES

        self.refresh()
        self.reload_installed()

    # --- data ---
    def refresh(self):
        self.refresh_btn.setEnabled(False)
        self.statusbar.showMessage("Загрузка списка…")
        self.worker = FetchWorker()
        self.worker.done.connect(self.on_fetched)
        self.worker.failed.connect(self.on_fetch_failed)
        self.worker.start()

    def on_fetched(self, data: dict):
        self.by_source = data
        self.latest_tags = {v[0].tag for v in data.values() if v}
        self.refresh_btn.setEnabled(True)
        total = sum(len(v) for v in data.values())
        self.statusbar.showMessage(f"Найдено релизов: {total}")
        self.rebuild_sidebar()
        self.rebuild_cards()

    def on_fetch_failed(self, err: str):
        self.refresh_btn.setEnabled(True)
        self.statusbar.showMessage(f"Ошибка: {err}")

    def rebuild_sidebar(self):
        cur = self.sidebar.currentRow() if self.sidebar.count() else 0
        self.sidebar.clear()
        for name in SOURCE_NAMES:
            n = sum(len(v) for v in self.by_source.values()) if name == "Все" \
                else len(self.by_source.get(name, []))
            QListWidgetItem(f"{name} ({n})", self.sidebar)
        self.sidebar.setCurrentRow(max(0, cur))

    def current_source(self) -> str:
        row = self.sidebar.currentRow()
        if 0 <= row < len(SOURCE_NAMES):
            return SOURCE_NAMES[row]
        return "Все"

    def filtered(self) -> list[Release]:
        src = self.current_source()
        rels = [r for v in self.by_source.values() for r in v] if src == "Все" \
            else list(self.by_source.get(src, []))
        q = self.search.text().strip().lower()
        if q:
            rels = [r for r in rels if q in r.tag.lower()]
        mode = self.sort_combo.currentIndex()
        if mode == 0:
            rels.sort(key=lambda r: r.published_at or "", reverse=True)
        elif mode == 1:
            rels.sort(key=lambda r: r.published_at or "")
        elif mode == 2:
            rels.sort(key=lambda r: r.size or 0, reverse=True)
        elif mode == 3:
            rels.sort(key=lambda r: r.size or 0)
        return rels

    def rebuild_cards(self):
        # clear
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards.clear()
        for r in self.filtered():
            installed = bool(possible_dir_names(r) & self.installed)
            card = ReleaseCard(r, is_latest=r.tag in self.latest_tags,
                               is_installed=installed)
            card.install_clicked.connect(self.install_release)
            card.remove_clicked.connect(self.remove_release)
            key = f"{r.source}\0{r.tag}"
            self.cards[key] = card
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        if not self.filtered():
            self.cards_layout.insertWidget(
                0, QLabel("Ничего не найдено. Обновите список или измените поиск."))

    # --- install dir ---
    def browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Папка установки")
        if d:
            self.dir_edit.setText(d)

    def install_dir(self) -> Path:
        return Path(self.dir_edit.text()).expanduser()

    def reload_installed(self):
        try:
            names = list_installed(self.install_dir())
        except Exception:  # noqa: BLE001
            names = []
        self.installed = {n.lower() for n in names}
        if self.cards:
            self.rebuild_cards()

    # --- actions ---
    def install_release(self, r: Release):
        if self.active_card is not None:
            QMessageBox.information(self, "Подождите", "Уже идёт загрузка.")
            return
        key = f"{r.source}\0{r.tag}"
        card = self.cards.get(key)
        self.active_card = card
        self.refresh_btn.setEnabled(False)
        self.worker = DownloadWorker(r, self.install_dir())
        self.worker.progress.connect(
            lambda d, t: card.set_progress(d, t) if card else None)
        self.worker.done.connect(lambda target: self.on_installed(target, r))
        self.worker.failed.connect(self.on_install_failed)
        self.statusbar.showMessage(f"Скачивание {r.tag}…")
        self.worker.start()

    def on_installed(self, target: str, r: Release):
        self.refresh_btn.setEnabled(True)
        if self.active_card:
            self.active_card.clear_progress()
        self.active_card = None
        self.statusbar.showMessage(f"Установлено: {target}")
        QMessageBox.information(self, "Готово",
                                f"Установлено в:\n{target}\n\nПерезапустите Steam.")
        self.reload_installed()

    def on_install_failed(self, err: str):
        self.refresh_btn.setEnabled(True)
        if self.active_card:
            self.active_card.clear_progress()
        self.active_card = None
        self.statusbar.showMessage("Ошибка установки")
        QMessageBox.critical(self, "Ошибка", err)

    def remove_release(self, r: Release):
        cands = possible_dir_names(r) & self.installed
        if not cands:
            # fallback: match by tag containment
            cands = {n for n in self.installed if r.tag.lower() in n or n in r.tag.lower()}
        if not cands:
            QMessageBox.information(self, "Не найдено", "Сборка не найдена в папке установки.")
            return
        # resolve original-case name
        real = next((n for n in list_installed(self.install_dir()) if n.lower() in cands), None)
        if real is None:
            return
        if QMessageBox.question(self, "Удалить", f"Удалить {real}?") != QMessageBox.Yes:
            return
        remove_build(self.install_dir(), real)
        self.reload_installed()


def main():
    import sys
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # системная палитра, нативный вид в light/dark
    app.setStyleSheet(QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
