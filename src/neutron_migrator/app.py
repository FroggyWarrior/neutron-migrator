from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .config import Settings
from .engine.proton_cli import ProtonCliEngine
from .i18n import I18n
from .theme import ThemeManager


@dataclass
class Context:
    settings: Settings
    i18n: I18n
    themes: ThemeManager
    engine: RcloneEngine
    account: str = ""
    go: Callable = field(default=lambda *a, **k: None)