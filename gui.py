"""PySide6 GUI: sidebar + cards, system theme, search + badges."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter,
    QStatusBar, QVBoxLayout, QWidget,
)

from downloader import DownloadCancelled, download, fetch_expected_sha512, verify_sha512
from fetcher import SOURCES, fetch_all, load_cached_releases
from installer import (
    InstallCancelled, cleanup_archive, default_dir_for_target, dir_size, extract_archive,
    installed_total_size, list_installed, prune_old_builds, remove_build,
    target_hint, target_ids, target_label,
)
from settings import load_settings, save_settings
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
            cached = load_cached_releases()
            if cached and sum(len(v) for v in cached.values()):
                self.done.emit(cached)
            else:
                self.failed.emit(str(e))


class DownloadWorker(QThread):
    progress = Signal(int, int, float, float)  # done, total, speed_bps, eta_s (-1 = ?)
    extract_progress = Signal(int, int)
    phase = Signal(str)
    done = Signal(object)  # {"target": str, "pruned": list}
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, release: Release, install_dir: Path,
                 delete_archive: bool = True, keep_n: int = 0):
        super().__init__()
        self.release = release
        self.install_dir = install_dir
        self.delete_archive = delete_archive
        self.keep_n = keep_n

    def run(self):
        try:
            tmp = Path(tempfile.gettempdir()) / "proton-downloader"
            tmp.mkdir(parents=True, exist_ok=True)
            fname = self.release.url.split("/")[-1].split("?")[0] or "proton-archive"
            archive = tmp / fname
            self.phase.emit("Скачивание…")
            t0 = time.monotonic()
            # первичное уведомление чтобы показать бар сразу
            self.progress.emit(0, self.release.size or 0, 0.0, -1.0)

            def _prog(d: int, t: int):
                el = max(time.monotonic() - t0, 0.01)
                speed = d / el
                eta = (t - d) / speed if t and speed > 0 else -1.0
                self.progress.emit(d, t, speed, eta)

            try:
                download(self.release.url, archive, progress=_prog,
                         is_cancelled=self.isInterruptionRequested)
            except DownloadCancelled:
                self.cancelled.emit()
                return
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            if self.release.checksum_url:
                self.phase.emit("Проверка SHA512…")
                expected = fetch_expected_sha512(self.release.checksum_url)
                if expected and not verify_sha512(archive, expected):
                    self.failed.emit("SHA512 mismatch — файл повреждён")
                    return
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            self.phase.emit("Распаковка…")
            try:
                target = extract_archive(
                    archive, self.install_dir,
                    progress=lambda d, t: self.extract_progress.emit(d, t),
                    is_cancelled=self.isInterruptionRequested)
            except InstallCancelled:
                self.cancelled.emit()
                return
            if self.delete_archive:
                cleanup_archive(archive)
            pruned: list[str] = []
            if self.keep_n > 0:
                pruned = prune_old_builds(self.install_dir, self.keep_n)
            self.done.emit({"target": str(target), "pruned": pruned})
        except Exception as e:  # noqa: BLE001
            if self.isInterruptionRequested():
                self.cancelled.emit()
            else:
                self.failed.emit(str(e))


def possible_dir_names(r: Release) -> set[str]:
    """Candidate installed-folder names for a release (lowercased)."""
    out = {r.tag.lower()}
    fname = r.url.split("/")[-1].split("?")[0]
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


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        s = load_settings()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("GitHub-токен (для снятия rate-limit 60/час):"))
        self.token = QLineEdit(s.get("github_token", ""))
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText("ghp_… (пусто = без токена)")
        lay.addWidget(self.token)
        lay.addWidget(QLabel("Держать сборок максимум (0 = без лимита):"))
        self.keep = QSpinBox()
        self.keep.setRange(0, 50)
        self.keep.setValue(int(s.get("keep_n", 0)))
        lay.addWidget(self.keep)
        self.del_arch = QCheckBox("Удалять архив после установки")
        self.del_arch.setChecked(bool(s.get("delete_archive_after_install", True)))
        lay.addWidget(self.del_arch)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def values(self) -> dict:
        s = load_settings()
        s["github_token"] = self.token.text().strip()
        s["keep_n"] = int(self.keep.value())
        s["delete_archive_after_install"] = bool(self.del_arch.isChecked())
        return s


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
        self.active_release: Release | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)

        # top bar: search + sort + refresh + url + settings
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
        self.url_btn = QPushButton("По URL…")
        self.url_btn.setToolTip("Установить сборку по прямой ссылке на .tar.gz/.tar.xz")
        self.url_btn.clicked.connect(self.install_by_url)
        top.addWidget(self.url_btn)
        self.settings_btn = QPushButton("Настройки")
        self.settings_btn.clicked.connect(self.open_settings)
        top.addWidget(self.settings_btn)
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
        # install target + dir (compact, in sidebar bottom)
        side_layout.addWidget(QLabel("Ставить в:"))
        self.target_combo = QComboBox()
        for tid in target_ids():
            self.target_combo.addItem(target_label(tid), tid)
        saved_target = load_settings().get("target", "steam")
        if saved_target not in target_ids():
            saved_target = "steam"
        self.target_combo.setCurrentIndex(target_ids().index(saved_target))
        self.target_combo.currentIndexChanged.connect(self.on_target_changed)
        side_layout.addWidget(self.target_combo)
        self.target_hint = QLabel(target_hint(saved_target))
        self.target_hint.setObjectName("CardMeta")
        self.target_hint.setWordWrap(True)
        side_layout.addWidget(self.target_hint)
        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit(str(default_dir_for_target(saved_target)))
        self.dir_edit.textChanged.connect(self.reload_installed)
        dir_row.addWidget(self.dir_edit, 1)
        browse = QPushButton("…")
        browse.setFixedWidth(36)
        browse.clicked.connect(self.browse_dir)
        dir_row.addWidget(browse)
        side_layout.addLayout(dir_row)
        self.disk_label = QLabel("")
        self.disk_label.setObjectName("CardMeta")
        side_layout.addWidget(self.disk_label)
        # prune row
        prune_row = QHBoxLayout()
        prune_row.addWidget(QLabel("Держать:"))
        self.keep_spin = QSpinBox()
        self.keep_spin.setRange(0, 50)
        self.keep_spin.setValue(int(load_settings().get("keep_n", 0)))
        self.keep_spin.setToolTip("0 = без лимита")
        self.keep_spin.valueChanged.connect(self._keep_changed)
        prune_row.addWidget(self.keep_spin)
        self.prune_btn = QPushButton("Почистить")
        self.prune_btn.setToolTip("Удалить старые сборки, оставив N самых новых")
        self.prune_btn.clicked.connect(self.prune_now)
        prune_row.addWidget(self.prune_btn)
        side_layout.addLayout(prune_row)
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
        # мгновенно показать кэш, если есть, затем обновить из сети
        cached = load_cached_releases()
        if cached and not self.by_source:
            self.on_fetched(cached, cached_note=True)
        self.statusbar.showMessage("Загрузка списка…")
        self.worker = FetchWorker()
        self.worker.done.connect(lambda d: self.on_fetched(d))
        self.worker.failed.connect(self.on_fetch_failed)
        self.worker.start()

    def on_fetched(self, data: dict, cached_note: bool = False):
        self.by_source = data
        self.latest_tags = {v[0].tag for v in data.values() if v}
        self.refresh_btn.setEnabled(True)
        total = sum(len(v) for v in data.values())
        msg = f"Найдено релизов: {total}"
        if cached_note:
            msg += " (кэш, обновление…)"
        self.statusbar.showMessage(msg)
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
            card.cancel_clicked.connect(self.cancel_active)
            if self.active_release and r.source == self.active_release.source \
                    and r.tag == self.active_release.tag:
                self.active_card = card
                card.set_busy(True, "Скачивание…")
            key = f"{r.source}\0{r.tag}"
            self.cards[key] = card
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        if not self.filtered():
            self.cards_layout.insertWidget(
                0, QLabel("Ничего не найдено. Обновите список или измените поиск."))

    # --- install dir ---
    def current_target(self) -> str:
        tid = self.target_combo.currentData()
        return tid if tid in target_ids() else "steam"

    def on_target_changed(self):
        tid = self.current_target()
        self.target_hint.setText(target_hint(tid))
        self.dir_edit.setText(str(default_dir_for_target(tid)))
        s = load_settings()
        s["target"] = tid
        save_settings(s)
        self.reload_installed()

    def browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Папка установки")
        if d:
            self.dir_edit.setText(d)

    def install_dir(self) -> Path:
        return Path(self.dir_edit.text()).expanduser()

    def reload_installed(self):
        try:
            names = list_installed(self.install_dir())
            total = installed_total_size(self.install_dir())
        except Exception:  # noqa: BLE001
            names = []
            total = 0
        self.installed = {n.lower() for n in names}
        mb = total / 1024 / 1024
        self.disk_label.setText(f"Установлено: {len(names)} · {mb:.0f} МБ")
        if self.cards:
            self.rebuild_cards()

    def _keep_changed(self, v: int):
        s = load_settings()
        s["keep_n"] = int(v)
        save_settings(s)

    def prune_now(self):
        n = int(self.keep_spin.value())
        if n <= 0:
            QMessageBox.information(self, "Очистка",
                                    "Укажите «Держать» > 0 (сколько новых сборок оставить).")
            return
        names = list_installed(self.install_dir())
        if len(names) <= n:
            QMessageBox.information(self, "Очистка", "Чистить нечего — сборок не больше лимита.")
            return
        if QMessageBox.question(
                self, "Очистка",
                f"Оставить {n} самых новых, остальные {len(names) - n} удалить?") != QMessageBox.Yes:
            return
        pruned = prune_old_builds(self.install_dir(), n)
        self.reload_installed()
        self.statusbar.showMessage(f"Удалено старых сборок: {len(pruned)}")

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            save_settings(dlg.values())
            self.keep_spin.setValue(int(dlg.values().get("keep_n", 0)))
            self.statusbar.showMessage("Настройки сохранены")

    def install_by_url(self):
        url, ok = QInputDialog.getText(self, "Установка по URL",
                                       "Прямая ссылка на .tar.gz / .tar.xz:")
        if not ok or not url.strip():
            return
        url = url.strip()
        fname = url.split("/")[-1].split("?")[0]
        if not fname.endswith((".tar.gz", ".tgz", ".tar.xz", ".tar.bz2")):
            QMessageBox.warning(self, "URL", "Нужна ссылка на архив .tar.gz / .tar.xz")
            return
        tag = fname
        for suffix in (".tar.gz", ".tgz", ".tar.xz", ".tar.bz2"):
            if tag.endswith(suffix):
                tag = tag[: -len(suffix)]
                break
        r = Release(source="URL", tag=tag, name=tag, url=url, size=0,
                    checksum_url=None, published_at="", body="")
        self.install_release(r, card_key=None)

    # --- actions ---
    def install_release(self, r: Release, card_key: str | None = None):
        if isinstance(self.worker, DownloadWorker) and self.worker.isRunning():
            QMessageBox.information(self, "Подождите", "Уже идёт загрузка. Отмените её для новой.")
            return
        key = card_key or f"{r.source}\0{r.tag}"
        card = self.cards.get(key)
        self.active_card = card
        self.active_release = r
        s = load_settings()
        if card:
            card.set_busy(True, "Скачивание…")
        self.refresh_btn.setEnabled(False)
        self.worker = DownloadWorker(r, self.install_dir(),
                                     delete_archive=bool(s.get("delete_archive_after_install", True)),
                                     keep_n=int(s.get("keep_n", 0)))
        if card:
            self.worker.progress.connect(
                lambda d, t, sp, eta: (card.set_progress(d, t, sp, eta if eta >= 0 else None),
                                       self.statusbar.showMessage(f"Скачивание {r.tag}…")))
            self.worker.extract_progress.connect(card.set_extract_progress)
            self.worker.phase.connect(card.set_phase)
        else:
            self.worker.progress.connect(
                lambda d, t, sp, eta: self.statusbar.showMessage(f"Скачивание {r.tag}…"))
        self.worker.done.connect(lambda info: self.on_installed(info, r))
        self.worker.failed.connect(self.on_install_failed)
        self.worker.cancelled.connect(lambda: self.on_install_cancelled(r))
        self.statusbar.showMessage(f"Скачивание {r.tag}…")
        self.worker.start()

    def cancel_active(self, _r: Release | None = None):
        if isinstance(self.worker, DownloadWorker) and self.worker.isRunning():
            self.worker.requestInterruption()
            self.statusbar.showMessage("Отмена…")

    def on_installed(self, info: object, r: Release):
        target = info.get("target", "") if isinstance(info, dict) else str(info)
        pruned = info.get("pruned", []) if isinstance(info, dict) else []
        self.refresh_btn.setEnabled(True)
        if self.active_card:
            self.active_card.clear_progress()
        self.active_card = None
        self.active_release = None
        msg = f"Установлено: {target}"
        if pruned:
            msg += f" (удалено старых: {len(pruned)})"
        self.statusbar.showMessage(msg)
        msg = f"Установлено в:\n{target}\n\n"
        if self.current_target() == "steam":
            msg += "Перезапустите Steam."
        else:
            msg += target_hint(self.current_target())
        QMessageBox.information(self, "Готово", msg)
        self.reload_installed()

    def on_install_failed(self, err: str):
        self.refresh_btn.setEnabled(True)
        if self.active_card:
            self.active_card.clear_progress()
        self.active_card = None
        self.active_release = None
        self.statusbar.showMessage("Ошибка установки")
        QMessageBox.critical(self, "Ошибка", err)

    def on_install_cancelled(self, r: Release):
        self.refresh_btn.setEnabled(True)
        if self.active_card:
            self.active_card.clear_progress()
        self.active_card = None
        self.active_release = None
        self.statusbar.showMessage(f"Отменено: {r.tag}")
        self.reload_installed()

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
        try:
            sz = dir_size(self.install_dir() / real)
        except Exception:
            sz = 0
        remove_build(self.install_dir(), real)
        self.statusbar.showMessage(f"Удалено {real} ({sz / 1024 / 1024:.0f} МБ)")
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
