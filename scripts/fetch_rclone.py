#!/usr/bin/env python3
"""Download the Neutron Migrator engine (rclone) over HTTPS and verify its official SHA256.

Usage:
    python scripts/fetch_rclone.py                 # pinned version
    python scripts/fetch_rclone.py --version current
    python scripts/fetch_rclone.py --dest /some/dir
"""
from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

PINNED = "1.68.2"  # minimum supported by the app: 1.65
CHUNK = 1 << 20


def target_names(version: str) -> tuple[str, str, str]:
    """Return (base_url, archive_name, binary_name) for this platform."""
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "osx"}.get(platform.system())
    machine = platform.machine().lower()
    arch = {
        "x86_64": "amd64", "amd64": "amd64",
        "aarch64": "arm64", "arm64": "arm64",
        "i386": "386", "i686": "386", "x86": "386",
    }.get(machine)
    if not system or not arch:
        sys.exit(f"Unsupported platform: {platform.system()} {machine}. Install rclone 1.65+ manually.")
    tag = "current" if version == "current" else f"v{version.lstrip('v')}"
    base = "https://downloads.rclone.org" + ("" if tag == "current" else f"/{tag}")
    return base, f"rclone-{tag}-{system}-{arch}.zip", "rclone.exe" if system == "windows" else "rclone"


def find_checksum(sums_text: str, archive: str) -> str | None:
    """Parse SHA256SUMS, tolerating blank lines, comments and '*' binary markers."""
    for line in sums_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[-1].lstrip("*").removeprefix("./").strip()
        if name == archive:
            return parts[0].lower()
    return None


def download(url: str, destination: Path) -> str:
    """Stream a file to disk, returning its SHA256 hex digest."""
    digest = hashlib.sha256()
    written = 0
    with requests.get(url, stream=True, timeout=300) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or 0)
        with destination.open("wb") as handle:
            for chunk in response.iter_content(CHUNK):
                if not chunk:
                    continue
                handle.write(chunk)
                digest.update(chunk)
                written += len(chunk)
        if total and written != total:
            sys.exit(f"Incomplete download: got {written} of {total} bytes.")
    print(f"Downloaded {written / 1_048_576:.1f} MiB.")
    return digest.hexdigest().lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and verify the rclone engine.")
    parser.add_argument("--version", default=PINNED, help="rclone version, or 'current'")
    parser.add_argument("--dest", default=str(Path(__file__).resolve().parents[1] / "vendor" / "rclone"))
    args = parser.parse_args()

    base, archive, binary = target_names(args.version)
    dest_dir = Path(args.dest).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / binary

    print(f"Fetching checksums from {base}/SHA256SUMS …")
    try:
        sums = requests.get(f"{base}/SHA256SUMS", timeout=60)
        sums.raise_for_status()
    except requests.RequestException as exc:
        sys.exit(f"Could not download SHA256SUMS: {exc}")

    expected = find_checksum(sums.text, archive)
    if not expected:
        published = "\n".join(line for line in sums.text.splitlines() if line.strip())
        sys.exit(f"No checksum published for {archive}\n\nPublished files:\n{published}")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / archive
        print(f"Downloading {base}/{archive} …")
        try:
            actual = download(f"{base}/{archive}", zip_path)
        except requests.RequestException as exc:
            sys.exit(f"Download failed: {exc}")
        if actual != expected:
            sys.exit(f"SHA256 mismatch — download rejected.\nExpected: {expected}\nActual:   {actual}")
        print("Checksum OK.")

        try:
            with zipfile.ZipFile(zip_path) as zf:
                member = next(
                    (n for n in zf.namelist() if n == binary or n.endswith("/" + binary)), None
                )
                if member is None:
                    sys.exit(f"{binary} not found inside {archive}.")
                with zf.open(member) as src, out_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        except (zipfile.BadZipFile, OSError) as exc:
            sys.exit(f"Could not extract the engine: {exc}")

    out_path.chmod(out_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Engine ready: {out_path}")


if __name__ == "__main__":
    main()