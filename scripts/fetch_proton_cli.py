#!/usr/bin/env python3
"""Download the official Proton Drive CLI for one or more targets."""
from __future__ import annotations

import argparse
import hashlib
import platform
import stat
import sys
from pathlib import Path

import requests

VERSION = "0.9.0"
BASE = "https://proton.me/download/drive/cli"
TARGETS = {
    "windows-x64": "proton-drive.exe",
    "linux-x64": "proton-drive",
    "linux-x64-baseline": "proton-drive",
    "linux-arm64": "proton-drive",
    "darwin-arm64": "proton-drive",
    "darwin-x64": "proton-drive",
}


def host_target() -> str:
    system = {"win32": "windows", "linux": "linux", "darwin": "darwin"}[sys.platform]
    machine = platform.machine().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine, machine)
    target = f"{system}-{arch}"
    if target not in TARGETS:
        sys.exit(f"No official CLI build for {target}. Supported: {', '.join(TARGETS)}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--target", action="append", help="e.g. linux-x64 (repeatable)")
    parser.add_argument("--dest", default=str(Path(__file__).resolve().parents[1] / "vendor" / "proton-drive"))
    parser.add_argument("--sha512", help="optional pinned SHA-512 for a single target")
    args = parser.parse_args()

    targets = args.target or [host_target()]
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    for target in targets:
        if target not in TARGETS:
            sys.exit(f"Unknown target {target}. Supported: {', '.join(TARGETS)}")
        url = f"{BASE}/{args.version}/{target}/{TARGETS[target]}"
        # windows-arm64 hosts run the x64 build under emulation
        name = target.replace("darwin", "darwin")
        out = dest / f"proton-drive-{name}{'.exe' if target.startswith('windows') else ''}"
        print(f"Downloading {url}")
        digest = hashlib.sha512()
        with requests.get(url, stream=True, timeout=600) as response:
            response.raise_for_status()
            with out.open("wb") as handle:
                for chunk in response.iter_content(1 << 20):
                    handle.write(chunk)
                    digest.update(chunk)
        actual = digest.hexdigest()
        if args.sha512 and len(targets) == 1 and actual != args.sha512.lower():
            out.unlink(missing_ok=True)
            sys.exit(f"SHA-512 mismatch for {target}")
        out.chmod(out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  -> {out}\n  sha512: {actual}")


if __name__ == "__main__":
    main()