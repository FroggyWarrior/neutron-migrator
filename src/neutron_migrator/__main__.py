from __future__ import annotations

import sys
import traceback
import subprocess

from PySide6.QtWidgets import QApplication

from . import __app_name__, __developer__, __version__
from .app import Context
from .config import Settings, app_icon_path, data_dir
from .engine.proton_cli import ProtonCliEngine
from .errors import AppError
from .i18n import I18n
from .theme import ThemeManager
from .ui.main_window import MainWindow
from .ui.widgets import show_error
from PySide6.QtGui import QIcon


def _prepare_linux_qpa() -> None:
    """Qt's xcb plugin needs libxcb-cursor & friends; use bundled copies if absent."""
    if not sys.platform.startswith("linux"):
        return
    import ctypes
    import ctypes.util
    from pathlib import Path

    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    for name in ("xcb-util", "xcb-cursor", "xcb-icccm", "xcb-image", "xcb-keysyms",
                 "xcb-randr", "xcb-render-util", "xcb-shape", "xcb-xinerama",
                 "xcb-xkb", "xkbcommon-x11"):
        if ctypes.util.find_library(name):
            continue
        for candidate in sorted(base.glob(f"lib{name}.so.*")):
            try:
                ctypes.CDLL(str(candidate), mode=ctypes.RTLD_GLOBAL)
                break
            except OSError:
                continue
    try:
        ctypes.CDLL("libxcb-cursor.so.0", mode=ctypes.RTLD_GLOBAL)
    except OSError:
        message = ("Missing system library: libxcb-cursor.so.0\n"
                   "Debian/Ubuntu/Mint: sudo apt install libxcb-cursor0\n"
                   "Fedora: sudo dnf install xcb-util-cursor\n"
                   "Arch: sudo pacman -S xcb-util-cursor\n")
        sys.stderr.write(message)
        for tool in (["zenity", "--error", "--text"], ["kdialog", "--error"], ["xmessage"]):
            try:
                subprocess.run(tool + [message], check=False)
                break
            except OSError:
                continue
        sys.exit(1)


def main() -> None:
    _prepare_linux_qpa()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FroggyWarrior.NeutronMigrator")
        except Exception:
            pass

    QApplication.setDesktopFileName("neutron-migrator")
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__app_name__)
    app.setOrganizationName(__developer__)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(app_icon_path())))

    settings = Settings.load()
    i18n = I18n(settings.language)
    if settings.language != "system" and settings.language not in i18n.available():
        settings.language = "system"
        i18n.set_language("system")
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