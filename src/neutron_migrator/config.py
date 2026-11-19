from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_data_path

from . import __app_name__, __developer__

MIN_RCLONE = (1, 65, 0)


def asset(*parts: str) -> Path:
    """Resolve a bundled asset in dev and in PyInstaller (onedir/onefile) layouts."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates += [Path(meipass) / "neutron_migrator", Path(meipass)]
    candidates.append(Path(__file__).resolve().parent)
    for base in candidates:
        path = base.joinpath("assets", *parts)
        if path.exists():
            return path
    return candidates[0].joinpath("assets", *parts)


def data_dir() -> Path:
    path = user_data_path(__app_name__, __developer__)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


@dataclass
class Settings:
    language: str = "en"          # en | es | ...
    theme: str = "dark"           # dark | light | system
    keep_session: bool = False
    concurrency: int = 4
    delete_mode: str = "trash"    # trash | permanent
    scope: str = ""               # "" = whole Drive
    last_destination: str = ""
    _path: Path = field(default_factory=lambda: data_dir() / "settings.json", repr=False)

    @classmethod
    def load(cls) -> "Settings":
        path = data_dir() / "settings.json"
        s = cls(_path=path)
        try:
            raw = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return s
        for k, v in raw.items():
            if hasattr(s, k) and not k.startswith("_") and isinstance(v, type(getattr(s, k))):
                setattr(s, k, v)
        s.concurrency = max(1, min(8, s.concurrency))
        return s

    def save(self) -> None:
        payload = {k: v for k, v in vars(self).items() if not k.startswith("_")}
        try:
            self._path.write_text(json.dumps(payload, indent=2), "utf-8")
            os.chmod(self._path, 0o600)
        except OSError:
            pass