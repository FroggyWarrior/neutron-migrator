from __future__ import annotations

import platform
import sys
import traceback
from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QFont
from shiboken6 import isValid
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLayout, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)

from .. import __app_name__, __developer__, __version__, security
from ..errors import AppError


def label(i18n, key: str, style: str = "", wrap: bool = False, **params) -> QLabel:
    w = QLabel()
    if style:
        w.setObjectName(style)
    w.setWordWrap(wrap)
    i18n.bind(w, key, **params)
    return w


def button(i18n, key: str, kind: str = "", **params) -> QPushButton:
    b = QPushButton()
    if kind:
        b.setProperty("class", kind)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    i18n.bind(b, key, **params)
    return b


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(12)
    return frame, lay


def row(*widgets, spacing: int = 10) -> QWidget:
    holder = QWidget()
    holder.setObjectName("row")
    lay = QHBoxLayout(holder)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for w in widgets:
        lay.addWidget(w, 1 if isinstance(w, QWidget) and w.sizePolicy().horizontalStretch() else 0)
    return holder


def format_size(i18n, size: float) -> str:
    for unit, factor in (("size.tib", 1024 ** 4), ("size.gib", 1024 ** 3),
                         ("size.mib", 1024 ** 2), ("size.kib", 1024)):
        if size >= factor:
            return i18n.t(unit, value=f"{size / factor:.2f}")
    return i18n.t("size.b", value=int(size))


def format_eta(seconds: float | None) -> str:
    if seconds is None:
        return ""
    seconds = int(seconds)
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return f"{h}h {m:02d}m" if h else (f"{m}m {s:02d}s" if m else f"{s}s")


def build_debug(ctx, exc: BaseException) -> str:
    parts = [
        f"App: {__app_name__} {__version__} (developer: {__developer__})",
        f"Python: {sys.version.split()[0]} | Platform: {platform.platform()}",
        f"Engine: {ctx.engine.version} @ {ctx.engine.exe}",
        f"UI language: {ctx.i18n.language} | theme: {ctx.themes.mode} ({ctx.themes.effective()})",
        f"UTC time: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    if getattr(exc, "debug", ""):
        parts += ["Context:", exc.debug, ""]
    parts += ["Traceback:", "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
              "", "Engine log (tail):", ctx.engine.log_tail(80)]
    return security.redact("\n".join(parts))


class ErrorDialog(QDialog):
    def __init__(self, parent, ctx, message: str, debug: str, title_key: str = "common.error"):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._ctx = ctx
        self.setWindowTitle(ctx.i18n.t(title_key))
        self.setMinimumSize(700, 460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(14)
        lay.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        lay.addWidget(label(ctx.i18n, title_key, "h2"))
        body = QLabel(message)
        body.setWordWrap(True)
        body.setObjectName("body")
        body.setMinimumWidth(600)
        lay.addWidget(body)

        self.details = QPlainTextEdit(debug)
        self.details.setReadOnly(True)
        self.details.setFont(QFont("Monospace", 9))
        self.details.setMinimumHeight(260)
        self.details.setVisible(False)
        lay.addWidget(self.details)

        self.toggle = button(ctx.i18n, "common.show_more")
        self.toggle.clicked.connect(self._toggle)
        self.copy_btn = button(ctx.i18n, "common.copy")
        self.copy_btn.clicked.connect(self._copy)
        close = button(ctx.i18n, "common.close", "primary")
        close.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(self.toggle)
        buttons.addWidget(self.copy_btn)
        buttons.addStretch(1)
        buttons.addWidget(close)
        lay.addLayout(buttons)

    def _toggle(self) -> None:
        visible = not self.details.isVisible()
        self.details.setVisible(visible)
        self._ctx.i18n.bind(self.toggle, "common.show_less" if visible else "common.show_more")

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.details.toPlainText())
        self._ctx.i18n.bind(self.copy_btn, "common.copied")
        QTimer.singleShot(1500, self._restore_copy_label)

    def _restore_copy_label(self) -> None:
        if isValid(self.copy_btn):
            self._ctx.i18n.bind(self.copy_btn, "common.copy")


def show_error(parent, ctx, exc: BaseException) -> None:
    if isinstance(exc, AppError):
        message = ctx.i18n.t(exc.key, **exc.params)
    else:
        message = ctx.i18n.t("error.generic", message=f"{type(exc).__name__}: {exc}")
    ErrorDialog(parent, ctx, message, build_debug(ctx, exc)).exec()


def open_folder(path: str) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))