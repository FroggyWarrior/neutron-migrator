from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QObject, Signal
from shiboken6 import isValid

from .config import asset


class I18n(QObject):
    """JSON-backed translations with widget auto-rebinding (PySide6-safe)."""

    changed = Signal()

    def __init__(self, language: str = "en"):
        super().__init__()
        self._fallback = self._load("en")
        self._strings: dict[str, str] = {}
        # key: (id(widget), property) -> (widget, property, translation_key, params)
        self._bindings: dict[tuple[int, str], tuple[Any, str, str, dict]] = {}
        self.language = "en"
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
        return sorted(p.stem for p in asset("i18n").glob("*.json"))

    def display_name(self, lang: str) -> str:
        return self._load(lang).get("language.name", lang)

    def set_language(self, lang: str) -> None:
        self.language = lang if lang in self.available() else "en"
        self._strings = self._load(self.language)
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
        """Use the real Qt setter (setText, setPlaceholderText, setWindowTitle…)."""
        setter = getattr(widget, "set" + prop[:1].upper() + prop[1:], None)
        if callable(setter):
            setter(value)
        else:
            widget.setProperty(prop, value)  # writes through the meta-object

    def bind(self, widget: Any, key: str, prop: str = "text", **params) -> None:
        self._bindings[(id(widget), prop)] = (widget, prop, key, params)
        self._apply(widget, prop, self.t(key, **params))

    def _rebind(self) -> None:
        for handle, (widget, prop, key, params) in list(self._bindings.items()):
            if not isValid(widget):
                del self._bindings[handle]
                continue
            try:
                self._apply(widget, prop, self.t(key, **params))
            except RuntimeError:
                del self._bindings[handle]