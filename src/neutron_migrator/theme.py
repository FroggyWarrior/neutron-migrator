from __future__ import annotations

import json

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QGuiApplication, QPalette

from .config import asset


class ThemeManager(QObject):
    def __init__(self, app: QGuiApplication, mode: str = "dark"):
        super().__init__()
        self.app, self.mode = app, mode
        self._palettes = json.loads(asset("themes", "palettes.json").read_text("utf-8"))
        self._qss = asset("themes", "base.qss").read_text("utf-8")
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda *_: self.apply())
        self.apply()

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in ("dark", "light", "system") else "dark"
        self.apply()

    def effective(self) -> str:
        if self.mode != "system":
            return self.mode
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorScheme"):
            return "dark" if hints.colorScheme() == Qt.ColorScheme.Dark else "light"
        return "dark" if QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128 else "light"

    def apply(self) -> None:
        palette = self._palettes[self.effective()]
        qss = self._qss
        for token, value in palette.items():
            qss = qss.replace("{{" + token + "}}", value)
        self.app.setStyleSheet(qss)