#!/usr/bin/env python3
"""Download the official Proton Drive CLI, verified against Proton's published SHA-512."""
from __future__ import annotations

import argparse
import hashlib
import platform
import stat
import sys
from pathlib import Path

import requests

PINNED_VERSION = "0.9.0"
BASE = "https://proton.me/download/drive/cli"

# target -> (file name, official SHA-512 for PINNED_VERSION)
BUILDS = {
    "windows-x64": ("proton-drive.exe",
                    "c68f2725b21bd8eddf83b816a059beeab4f1d2f0bb459e6bb53d1b1b972ea971e9d"
                    "9f191d9cb2aa41f6560c04936aa60f28bb6382191cb0e4e51dd41d36c8bed"),
    "windows-arm64": ("proton-drive.exe",
                      "dbb64152dfb3b180f3f49c3e0a33d7daf159b42b041e0aa83b63fd008cadac4a7"
                      "bedd252014c426e0a9c06a2c5d355b88a697acc2dcfc32543ecaa6cad9cc0fd"),
    "linux-x64": ("proton-drive",
                  "3533025ba69ae112b64e3e01fbcc1ad0688136a4043f6cf6a72886967d85fdcd"
                  "9ec235479c2e113171614be5225bfba93427509a05ca5aa6071d924fa7e91ca8"),
    "linux-arm64": ("proton-drive",
                    "c8d5a6b174e57f06d05cb5483400b9963faf58e743b6b33706bb73ecff718047f"
                    "fce6b439994255b94b5b226b90d2e91bef7418ec96c1c3f5d8bf39b6cd01321"),
    "linux-x64-musl": ("proton-drive",
                       "8f99c3bc478ebc2948ca69c8576a48d83b3290d807ca61fac9b0f5d0a91c0d41"
                       "8e595232d67e2ae0173d2188963771afd4292aefafab3f64e808a61c4399d6ed"),
    "linux-arm64-musl": ("proton-drive",
                         "4b632e5e694f6d0825aaa57f39f99494aa6a46eac45e90d65daa10b2e4631604"
                         "6b627d3c1145cb9c7d58951735cc6e81c28cca44dda648b411315a28d04b2acf"),
    "darwin-arm64": ("proton-drive",
                     "3f4125de5e41dcc7f4e0e07e8d60737aa18f35c6ecc1ba3fce47ea97b331857e"
                     "efaf88e74671135af57122d4cb5439b817ec528f8df383550ac7810aeaf0217b"),
    "darwin-x64": ("proton-drive",
                   "a9fc830f38b680ef537fd92db75e1d6e345374f977efa523b145ccc7ec98570"
                   "756f6ca32378d1bad6a84c9542f24ef43a63c6ec956e5dda9ca731b60b001a6e6"),
}


def host_target() -> str:
    system = {"win32": "windows", "linux": "linux", "darwin": "darwin"}[sys.platform]
    machine = platform.machine().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine, machine)
    target = f"{system}-{arch}"
    if target not in BUILDS:
        sys.exit(f"No official CLI build for {target}. Available: {', '.join(BUILDS)}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=PINNED_VERSION)
    parser.add_argument("--target", action="append", help="e.g. linux-x64 (repeatable)")
    parser.add_argument("--dest", default=str(Path(__file__).resolve().parents[1] / "vendor" / "proton-drive"))
    parser.add_argument("--sha512", help="override the expected checksum (single target)")
    args = parser.parse_args()

    targets = args.target or [host_target()]
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    for target in targets:
        if target not in BUILDS:
            sys.exit(f"Unknown target {target}. Available: {', '.join(BUILDS)}")
        filename, pinned = BUILDS[target]
        expected = args.sha512.lower() if args.sha512 else (pinned if args.version == PINNED_VERSION else None)
        url = f"{BASE}/{args.version}/{target}/{filename}"
        suffix = ".exe" if target.startswith("windows") else ""
        out = dest / f"proton-drive-{target}{suffix}"

        print(f"Downloading {url}")
        digest = hashlib.sha512()
        with requests.get(url, stream=True, timeout=600) as response:
            response.raise_for_status()
            with out.open("wb") as handle:
                for chunk in response.iter_content(1 << 20):
                    handle.write(chunk)
                    digest.update(chunk)
        actual = digest.hexdigest()
        if expected and actual != expected:
            out.unlink(missing_ok=True)
            sys.exit(f"SHA-512 mismatch for {target}\nExpected: {expected}\nActual:   {actual}")
        out.chmod(out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        status = "verified against Proton's published checksum" if expected else "UNVERIFIED (no pinned hash)"
        print(f"  -> {out}\n  {status}\n  sha512: {actual}")


if __name__ == "__main__":
    main()