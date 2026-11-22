from __future__ import annotations

import json
import re

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QGuiApplication, QPalette

from .config import asset


class ThemeManager(QObject):
    def __init__(self, app: QGuiApplication, mode: str = "system"):
        super().__init__()
        self.app, self.mode = app, mode
        self._palettes = json.loads(asset("themes", "palettes.json").read_text("utf-8"))
        self._qss = asset("themes", "base.qss").read_text("utf-8")
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda *_: self.apply())
        self.apply()

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in ("dark", "light", "system") else "system"
        self.apply()

    def effective(self) -> str:
        if self.mode != "system":
            return self.mode
        hints = QGuiApplication.styleHints()
        try:
            scheme = hints.colorScheme()
        except AttributeError:
            scheme = None
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
        if scheme == Qt.ColorScheme.Light:
            return "light"
        return "dark"          # unknown / unsupported -> dark

    def apply(self) -> None:
        palette = self._palettes[self.effective()]
        qss = self._qss
        for token, value in palette.items():
            qss = qss.replace("{{" + token + "}}", value)
        # Leftover {{tokens}} would inject literal braces and break the whole sheet.
        qss = re.sub(r"\{\{[A-Za-z0-9_]+\}\}", palette.get("muted", "#888888"), qss)
        self.app.setStyleSheet(qss)