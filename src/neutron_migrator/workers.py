from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    """Runs fn(cancel: Event, report: Callable) off the UI thread."""

    ok = Signal(object)
    fail = Signal(object)
    progress = Signal(object)

    def __init__(self, fn: Callable, parent=None):
        super().__init__(parent)
        self._fn = fn
        self.cancel_event = threading.Event()

    def run(self) -> None:  # noqa: D102
        try:
            self.ok.emit(self._fn(self.cancel_event, self.progress.emit))
        except BaseException as exc:  # noqa: BLE001 - forwarded to the UI handler
            self.fail.emit(exc)

    def cancel(self) -> None:
        self.cancel_event.set()


def run(parent, fn: Callable, on_ok: Callable, on_fail: Callable, on_progress: Callable | None = None) -> Worker:
    worker = Worker(fn, parent)
    worker.ok.connect(on_ok)
    worker.fail.connect(on_fail)
    if on_progress:
        worker.progress.connect(on_progress)
    worker.start()
    return worker