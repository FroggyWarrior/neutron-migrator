from __future__ import annotations

import json
import os
from typing import Any

from PySide6.QtCore import QLocale, QObject, Signal
from shiboken6 import isValid

from .config import asset

SYSTEM = "system"
FALLBACK = "en"


def available_languages() -> list[str]:
    return sorted(path.stem for path in asset("i18n").glob("*.json"))


def system_language() -> str:
    """Resolve the OS UI language to a shipped translation, or English."""
    candidates: list[str] = []
    locale = QLocale.system()
    try:
        candidates.extend(locale.uiLanguages())
    except Exception:
        pass
    candidates.append(locale.name())
    for variable in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        candidates.extend(os.environ.get(variable, "").split(":"))
    available = set(available_languages())
    for raw in candidates:
        code = raw.strip().replace("-", "_").split(".")[0].split("@")[0].lower()
        if not code or code in ("c", "posix"):
            continue
        if code in available:            # e.g. pt_BR if we ever ship a regional file
            return code
        base = code.split("_")[0]
        if base in available:
            return base
    return FALLBACK


class I18n(QObject):
    """JSON-backed translations with widget auto-rebinding (PySide6-safe)."""

    changed = Signal()

    def __init__(self, language: str = SYSTEM):
        super().__init__()
        self._fallback = self._load(FALLBACK)
        self._strings: dict[str, str] = {}
        self._bindings: dict[tuple[int, str], tuple[Any, str, str, dict]] = {}
        self.requested = SYSTEM
        self.language = FALLBACK
        self.set_language(language)

    # ------------------------------------------------------------------ loading
    @staticmethod
    def _load(lang: str) -> dict[str, str]:
        try:
            return json.loads(asset("i18n", f"{lang}.json").read_text("utf-8"))
        except (OSError, ValueError):
            return {}

    @staticmethod
    def available() -> list[str]:
        return available_languages()

    def display_name(self, lang: str) -> str:
        if lang == SYSTEM:
            return self.t("language.system")
        return self._load(lang).get("language.name", lang)

    def set_language(self, lang: str) -> None:
        self.requested = lang or SYSTEM
        if self.requested == SYSTEM:
            resolved = system_language()
        else:
            resolved = self.requested if self.requested in self.available() else FALLBACK
        self.language = resolved
        self._strings = self._load(resolved)
        self._rebind()
        self.changed.emit()

    def t(self, key: str, **params) -> str:
        text = self._strings.get(key) or self._fallback.get(key) or key
        if params:
            try:
                return text.format(**params)
            except (KeyError, IndexError):
                return text
        return text

    # ------------------------------------------------------------------ binding
    @staticmethod
    def _apply(widget: Any, prop: str, value: str) -> None:
        setter = getattr(widget, "set" + prop[:1].upper() + prop[1:], None)
        if callable(setter):
            setter(value)
        else:
            widget.setProperty(prop, value)

    def bind(self, widget: Any, key: str, prop: str = "text", **params) -> None:
        self._bindings[(id(widget), prop)] = (widget, prop, key, params)
        self._apply(widget, prop, self.t(key, **params))

    def unbind(self, widget: Any, prop: str = "text") -> None:
        """Forget a binding, so a later retranslate cannot restore stale text."""
        self._bindings.pop((id(widget), prop), None)

    def _rebind(self) -> None:
        for handle, (widget, prop, key, params) in list(self._bindings.items()):
            if not isValid(widget):
                del self._bindings[handle]
                continue
            try:
                self._apply(widget, prop, self.t(key, **params))
            except RuntimeError:
                del self._bindings[handle]