from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication

from . import __app_name__, __developer__, __version__
from .app import Context
from .config import Settings, data_dir
from .engine.proton_cli import ProtonCliEngine
from .errors import AppError
from .i18n import I18n
from .theme import ThemeManager
from .ui.main_window import MainWindow
from .ui.widgets import show_error


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__app_name__)
    app.setOrganizationName(__developer__)
    app.setApplicationVersion(__version__)

    settings = Settings.load()
    i18n = I18n(settings.language)
    themes = ThemeManager(app, settings.theme)
    engine = ProtonCliEngine(data_dir())
    ctx = Context(settings=settings, i18n=i18n, themes=themes, engine=engine)

    window = MainWindow(ctx)
    window.show()

    def hook(exc_type, exc, tb):
        show_error(window, ctx, AppError("error.generic", message=str(exc),
                                        debug="".join(traceback.format_exception(exc_type, exc, tb))))

    sys.excepthook = hook
    code = app.exec()
    engine.shutdown(keep=bool(settings.keep_session and ctx.account and engine.can_persist))
    sys.exit(code)


if __name__ == "__main__":
    main()