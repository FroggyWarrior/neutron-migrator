from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

SERVICE = "Neutron Migrator"
_KEY_USER = "rclone-config-key"
_SECRETS: set[str] = set()

_PATTERNS = (
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r'("(?:AccessToken|RefreshToken|SaltedKeyPass|password|pass|client_auth|Authorization)"\s*:\s*")[^"]+', re.I),
    re.compile(r"(x-pm-uid:\s*)\S+", re.I),
)


def remember(value: str | None) -> None:
    if value and len(value) > 3:
        _SECRETS.add(value)


def redact(text: str) -> str:
    for s in sorted(_SECRETS, key=len, reverse=True):
        text = text.replace(s, "***REDACTED***")
    for p in _PATTERNS:
        text = p.sub(lambda m: m.group(1) + "***REDACTED***", text)
    return text


def config_key() -> tuple[str, bool]:
    """Key that encrypts the engine config file. Returns (key, persisted_ok)."""
    try:
        import keyring
    except Exception:
        key = secrets.token_urlsafe(48)
        remember(key)
        return key, False


def restrict(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def wipe(path: Path) -> None:
    """Best-effort overwrite + unlink of the session file."""
    try:
        if path.exists():
            size = path.stat().st_size
            with path.open("r+b") as fh:
                fh.write(secrets.token_bytes(max(size, 512)))
                fh.flush()
                os.fsync(fh.fileno())
            path.unlink()
    except OSError:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass