"""Card widget for a single Proton release."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout,
)

from sources import Release


def fmt_size(n: int) -> str:
    if not n:
        return "?"
    return f"{n / 1024 / 1024:.0f} МБ"


class ReleaseCard(QFrame):
    install_clicked = Signal(object)  # Release
    remove_clicked = Signal(object)  # Release

    def __init__(self, release: Release, is_latest: bool = False,
                 is_installed: bool = False, parent=None):
        super().__init__(parent)
        self.release = release
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

        # bottom row: action + progress
        bottom = QHBoxLayout()
        self.action_btn = QPushButton("Удалить" if is_installed else "Установить")
        self.action_btn.setMinimumWidth(120)
        if is_installed:
            self.action_btn.clicked.connect(lambda: self.remove_clicked.emit(self.release))
        else:
            self.action_btn.clicked.connect(lambda: self.install_clicked.emit(self.release))
        bottom.addWidget(self.action_btn)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        bottom.addWidget(self.progress, 1)
        root.addLayout(bottom)

    @staticmethod
    def _badges(is_latest: bool, is_installed: bool) -> list[tuple[str, str]]:
        out = []
        if is_latest:
            out.append(("Latest", "Latest"))
        if is_installed:
            out.append(("Installed", "Installed"))
        return out

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

    def set_progress(self, done: int, total: int):
        self.progress.setVisible(True)
        if total:
            self.progress.setMaximum(100)
            self.progress.setValue(int(done * 100 / total))
            self.progress.setFormat(f"{done / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} МБ")
        else:
            self.progress.setMaximum(0)
            self.progress.setFormat(f"{done / 1024 / 1024:.0f} МБ")

    def clear_progress(self):
        self.progress.setVisible(False)
