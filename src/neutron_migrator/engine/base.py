from __future__ import annotations

from dataclasses import dataclass, field

PHOTO_EXTENSIONS = frozenset({
    "jpg", "jpeg", "jpe", "png", "heic", "heif", "hif", "avif", "jxl", "webp", "gif",
    "bmp", "tif", "tiff", "dng", "raw", "cr2", "cr3", "nef", "nrw", "arw", "srf",
    "raf", "orf", "rw2", "srw", "pef", "x3f", "3fr", "erf",
})

VIDEO_EXTENSIONS = frozenset({
    "mp4", "mov", "m4v", "avi", "mkv", "webm", "3gp", "3g2", "mts", "m2ts",
    "mpg", "mpeg", "wmv", "hevc", "insv",
})


def is_video(path: str) -> bool:
    return path.rsplit(".", 1)[-1].lower() in VIDEO_EXTENSIONS if "." in path else False

PHOTO_FOLDER_HINTS = ("my photos", "mis fotos", "mis fotografías", "photos", "fotos", "mes photos", "meine fotos")


def is_photo(path: str) -> bool:
    return path.rsplit(".", 1)[-1].lower() in PHOTO_EXTENSIONS if "." in path else False


@dataclass(frozen=True)
class Photo:
    path: str          # node UID
    size: int
    name: str = ""


@dataclass
class ScanResult:
    photos: list[Photo] = field(default_factory=list)
    unknown_sizes: int = 0
    videos: int = 0
    video_bytes: int = 0

    @property
    def count(self) -> int:
        return len(self.photos)

    @property
    def total_bytes(self) -> int:
        return sum(p.size for p in self.photos)


@dataclass
class Progress:
    done_files: int = 0
    total_files: int = 0
    done_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    eta: float | None = None
    current: str = ""
    stage: str = ""          # "" | "empty_trash"


@dataclass
class BatchResult:
    kind: str                # download | trash | permanent
    total: int
    done: int
    total_bytes: int
    done_bytes: int
    failures: list[tuple[str, str]] = field(default_factory=list)
    cancelled: bool = False
    warning_key: str = ""
    warning_debug: str = ""
    retry_photos: list = field(default_factory=list)