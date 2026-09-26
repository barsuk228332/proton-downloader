"""Card widget for a single Proton release."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QTextBrowser, QVBoxLayout,
)

from sources import Release


def fmt_size(n: int) -> str:
    if not n:
        return "?"
    return f"{n / 1024 / 1024:.0f} МБ"


def fmt_speed(bps: float) -> str:
    if bps <= 0:
        return "…"
    mb = bps / 1024 / 1024
    if mb >= 1:
        return f"{mb:.1f} МБ/с"
    return f"{bps / 1024:.0f} КБ/с"


def fmt_eta(sec: float | None) -> str:
    if sec is None or sec < 0 or sec == float("inf"):
        return ""
    s = int(sec)
    if s < 60:
        return f" · {s}с"
    m, s = divmod(s, 60)
    if m < 60:
        return f" · {m:02d}:{s:02d}"
    h, m = divmod(m, 60)
    return f" · {h}ч {m:02d}м"


class ChangelogDialog(QDialog):
    def __init__(self, release: Release, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{release.tag} — что нового")
        self.resize(560, 420)
        lay = QVBoxLayout(self)
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        text = (release.body or "Описание отсутствует.").strip()[:20000]
        view.setPlainText(text)
        lay.addWidget(view)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignRight)


class ReleaseCard(QFrame):
    install_clicked = Signal(object)  # Release
    remove_clicked = Signal(object)  # Release
    cancel_clicked = Signal(object)  # Release

    def __init__(self, release: Release, is_latest: bool = False,
                 is_installed: bool = False, parent=None):
        super().__init__(parent)
        self.release = release
        self.busy = False
        self.setObjectName("ReleaseCard")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # header: tag + badges
        header = QHBoxLayout()
        self.title = QLabel(release.tag)
        self.title.setObjectName("CardTitle")
        header.addWidget(self.title, 1)
        for text, kind in self._badges(is_latest, is_installed):
            b = QLabel(text)
            b.setObjectName(f"Badge_{kind}")
            b.setAlignment(Qt.AlignCenter)
            header.addWidget(b)
        root.addLayout(header)

        # meta line
        date = (release.published_at or "")[:10]
        meta = QLabel(f"{release.source}  ·  {date}  ·  {fmt_size(release.size)}")
        meta.setObjectName("CardMeta")
        root.addWidget(meta)

        # bottom row: action + changelog + progress + cancel
        bottom = QHBoxLayout()
        self.action_btn = QPushButton("Удалить" if is_installed else "Установить")
        self.action_btn.setMinimumWidth(120)
        if is_installed:
            self.action_btn.clicked.connect(lambda: self.remove_clicked.emit(self.release))
        else:
            self.action_btn.clicked.connect(lambda: self.install_clicked.emit(self.release))
        bottom.addWidget(self.action_btn)
        if release.body:
            self.changelog_btn = QPushButton("Что нового")
            self.changelog_btn.setMaximumWidth(110)
            self.changelog_btn.clicked.connect(self.show_changelog)
            bottom.addWidget(self.changelog_btn)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        bottom.addWidget(self.progress, 1)
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setMaximumWidth(90)
        self.cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.release))
        bottom.addWidget(self.cancel_btn)
        root.addLayout(bottom)

        # extraction/status label (скрыта по умолчанию)
        self.phase = QLabel("")
        self.phase.setObjectName("CardMeta")
        self.phase.setVisible(False)
        root.addWidget(self.phase)

    @staticmethod
    def _badges(is_latest: bool, is_installed: bool) -> list[tuple[str, str]]:
        out = []
        if is_latest:
            out.append(("Latest", "Latest"))
        if is_installed:
            out.append(("Installed", "Installed"))
        return out

    def show_changelog(self):
        ChangelogDialog(self.release, self).exec()

    def set_installed(self, installed: bool):
        self.action_btn.setText("Удалить" if installed else "Установить")
        try:
            self.action_btn.clicked.disconnect()
        except RuntimeError:
            pass
        if installed:
            self.action_btn.clicked.connect(lambda: self.remove_clicked.emit(self.release))
        else:
            self.action_btn.clicked.connect(lambda: self.install_clicked.emit(self.release))

    def set_busy(self, busy: bool, phase_text: str = ""):
        self.busy = busy
        self.action_btn.setEnabled(not busy)
        self.cancel_btn.setVisible(busy)
        if phase_text:
            self.phase.setText(phase_text)
            self.phase.setVisible(True)
        elif not busy:
            self.phase.setVisible(False)

    # --- progress with speed/ETA ---
    def set_progress(self, done: int, total: int, speed_bps: float = 0,
                     eta_s: float | None = None):
        self.progress.setVisible(True)
        if total:
            self.progress.setMaximum(100)
            self.progress.setValue(int(done * 100 / total))
            extra = ""
            if speed_bps > 0:
                extra = f" · {fmt_speed(speed_bps)}{fmt_eta(eta_s)}"
            self.progress.setFormat(
                f"{done / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} МБ{extra}")
        else:
            self.progress.setMaximum(0)
            self.progress.setFormat(f"{done / 1024 / 1024:.0f} МБ")

    def set_extract_progress(self, done: int, total: int):
        self.progress.setVisible(True)
        self.progress.setMaximum(total or 1)
        self.progress.setValue(done)
        self.progress.setFormat(f"Распаковка {done}/{total}")

    def set_phase(self, text: str):
        self.phase.setText(text)
        self.phase.setVisible(bool(text))

    def clear_progress(self):
        self.progress.setVisible(False)
        self.set_busy(False)
