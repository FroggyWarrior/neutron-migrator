from __future__ import annotations

import json


class AppError(Exception):
    """User-facing error: translated via `key`, plus English debug payload."""

    def __init__(self, key: str, *, debug: str = "", **params):
        super().__init__(key)
        self.key, self.params, self.debug = key, params, debug


class Cancelled(Exception):
    """Raised internally when the user cancels an operation."""


class Challenge(Exception):
    """An extra auth step is required: 'totp' | 'mailbox'."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


class RcError(Exception):
    """Raw engine (rclone RC) failure."""

    def __init__(self, endpoint: str, status: int, body: str):
        super().__init__(f"{endpoint} -> {status}")
        self.endpoint, self.status, self.body = endpoint, status, body

    @property
    def message(self) -> str:
        try:
            data = json.loads(self.body)
            return str(data.get("error") or data.get("Error") or self.body)[:600]
        except ValueError:
            return self.body[:600]

    def dump(self) -> str:
        return f"RC endpoint: {self.endpoint}\nHTTP status: {self.status}\nResponse:\n{self.body[:4000]}"