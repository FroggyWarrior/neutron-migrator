from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_data_path

from . import __app_name__, __developer__

# Only used by the legacy rclone engine; the Proton CLI engine ignores it.
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
    """Per-user writable directory for settings and engine state."""
    path = user_data_path(__app_name__, __developer__)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)  # directory: keep the execute bit
    except OSError:
        pass
    return path


@dataclass
class Settings:
    language: str = "en"            # en | es | ...
    theme: str = "system"          # dark | light | system
    keep_session: bool = False
    concurrency: int = 4
    delete_mode: str = "trash"      # trash | permanent
    scope: str = ""                 # "" = whole photo timeline
    last_destination: str = ""
    include_videos: bool = False
    _path: Path = field(default_factory=lambda: data_dir() / "settings.json", repr=False)

    @classmethod
    def load(cls) -> "Settings":
        path = data_dir() / "settings.json"
        settings = cls(_path=path)
        try:
            raw = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return settings
        if not isinstance(raw, dict):
            return settings
        for key, value in raw.items():
            if key.startswith("_") or not hasattr(settings, key):
                continue
            if isinstance(value, type(getattr(settings, key))):
                setattr(settings, key, value)
        settings.concurrency = max(1, min(8, settings.concurrency))
        if settings.theme not in ("dark", "light", "system"):
            settings.theme = "system"
        if settings.delete_mode not in ("trash", "permanent"):
            settings.delete_mode = "trash"
        return settings

    def save(self) -> None:
        payload = {key: value for key, value in vars(self).items() if not key.startswith("_")}
        try:
            self._path.write_text(json.dumps(payload, indent=2), "utf-8")
            os.chmod(self._path, 0o600)  # file: no execute bit needed
        except OSError:
            pass

def app_icon_path() -> Path:
    """Icon used for the window, taskbar and dock."""
    preferred = "icon.ico" if os.name == "nt" else "icon.png"
    for candidate in (asset("icons", preferred), asset("icons", "icon.png"),
                      Path(__file__).resolve().parents[2] / "packaging" / "icons" / "icon.png"):
        if candidate.exists():
            return candidate
    return asset("icons", "icon.png")