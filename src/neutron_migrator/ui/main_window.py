from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import __app_name__, __developer__
from .screens import ActionScreen, HomeScreen, LoginScreen, ProgressScreen, ResultScreen
from .widgets import label


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        from PySide6.QtGui import QIcon
        from ..config import app_icon_path
        self.setWindowIcon(QIcon(str(app_icon_path())))
        self.ctx = ctx
        ctx.go = self.go
        self.setMinimumSize(720, 620)
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("header")
        head = QHBoxLayout(header)
        head.setContentsMargins(28, 16, 28, 8)
        head.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label(ctx.i18n, "app.name", "h2"))
        titles.addWidget(label(ctx.i18n, "app.by", "muted", developer=__developer__))
        head.addLayout(titles)
        head.addStretch(1)
        head.addWidget(label(ctx.i18n, "header.theme", "muted"))
        self.theme_box = QComboBox()
        for mode, key in (("dark", "theme.dark"), ("light", "theme.light"), ("system", "theme.system")):
            self.theme_box.addItem(ctx.i18n.t(key), mode)
        self.theme_box.setCurrentIndex(max(0, self.theme_box.findData(ctx.settings.theme)))
        self.theme_box.currentIndexChanged.connect(self._theme_changed)
        head.addWidget(self.theme_box)
        head.addWidget(label(ctx.i18n, "header.language", "muted"))
        self.lang_box = QComboBox()
        self.lang_box.addItem(ctx.i18n.display_name("system"), "system")
        for lang in ctx.i18n.available():
            self.lang_box.addItem(ctx.i18n.display_name(lang), lang)
        self.lang_box.setCurrentIndex(max(0, self.lang_box.findData(ctx.settings.language)))
        self.lang_box.currentIndexChanged.connect(self._language_changed)
        head.addWidget(self.lang_box)
        outer.addWidget(header)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        ctx.i18n.changed.connect(self._retranslate)
        self._retranslate()
        self.go("login")

    # -- navigation
    def go(self, name: str, **kwargs) -> None:
        builders = {
            "login": lambda: LoginScreen(self.ctx),
            "home": lambda: HomeScreen(self.ctx),
            "action": lambda: ActionScreen(self.ctx, kwargs["kind"]),
            "progress": lambda: ProgressScreen(self.ctx, kwargs["kind"], kwargs["photos"],
                                               kwargs["destination"], kwargs["mode"]),
            "result": lambda: ResultScreen(self.ctx, kwargs["result"], kwargs["destination"]),
        }
        screen = builders[name]()
        old = self.stack.currentWidget()
        self.stack.addWidget(screen)
        self.stack.setCurrentWidget(screen)
        if old is not None:
            self.stack.removeWidget(old)
            old.deleteLater()

    # -- settings
    def _theme_changed(self) -> None:
        mode = self.theme_box.currentData()
        self.ctx.settings.theme = mode
        self.ctx.settings.save()
        self.ctx.themes.set_mode(mode)

    def _language_changed(self) -> None:
        lang = self.lang_box.currentData()
        self.ctx.settings.language = lang
        self.ctx.settings.save()
        self.ctx.i18n.set_language(lang)

    def _retranslate(self) -> None:
        self.setWindowTitle(f"{__app_name__} — {__developer__}")
        themes = [("theme.dark", "dark"), ("theme.light", "light"), ("theme.system", "system")]
        languages = [(None, "system")] + [(None, lang) for lang in self.ctx.i18n.available()]
        for box, values in ((self.theme_box, themes), (self.lang_box, languages)):
            current = box.currentData()
            box.blockSignals(True)
            for index, (key, data) in enumerate(values):
                box.setItemText(index, self.ctx.i18n.t(key) if key
                                else self.ctx.i18n.display_name(data))
            box.setCurrentIndex(max(0, box.findData(current)))
            box.blockSignals(False)

    def changeEvent(self, event) -> None:  # noqa: N802
        ctx = getattr(self, "ctx", None)
        if ctx is not None and event.type() == QEvent.Type.LocaleChange:
            if ctx.settings.language == "system":
                ctx.i18n.set_language("system")
        super().changeEvent(event)

    # -- shutdown
    def closeEvent(self, event) -> None:  # noqa: N802
        screen = self.stack.currentWidget()
        worker = getattr(screen, "worker", None)
        if worker is not None and worker.isRunning():
            answer = QMessageBox.question(self, self.ctx.i18n.t("common.quit_title"),
                                          self.ctx.i18n.t("common.quit_body"))
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            worker.cancel()
            if not worker.wait(8000):
                self.ctx.engine.shutdown(
                    keep=bool(self.ctx.settings.keep_session and self.ctx.account))
                worker.wait(3000)
            worker.wait(8000)
        event.accept()