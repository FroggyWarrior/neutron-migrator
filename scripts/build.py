#!/usr/bin/env python3
"""Build Neutron Migrator with PyInstaller on the current OS/arch.

Usage:
    python scripts/fetch_proton_cli.py      # once, downloads the Proton Drive CLI
    python scripts/build.py                 # onedir build + archive
    python scripts/build.py --onefile       # single-file build (slower startup)
    python scripts/build.py --no-package    # build only, skip archive
    python scripts/build.py --all-cli       # bundle every CLI binary in vendor/
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = "Neutron Migrator"
SEP = ";" if os.name == "nt" else ":"
SYSTEM = {"win32": "windows", "linux": "linux", "darwin": "darwin"}.get(sys.platform, sys.platform)

EXCLUDES = [
    "tkinter",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel",
    "PySide6.QtWebSockets", "PySide6.QtQuick3D", "PySide6.Qt3DCore", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtMultimedia", "PySide6.QtPdf",
    "PySide6.QtBluetooth", "PySide6.QtSerialPort", "PySide6.QtSensors",
    "PySide6.QtPositioning", "PySide6.QtNfc", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech",
]


def host_tag() -> str:
    machine = platform.machine().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine, machine)
    return f"{SYSTEM}-{arch}"


def select_binaries(vendor: Path, keep_all: bool) -> list[Path]:
    """Prefer arch-specific CLI builds; drop the plain duplicate and foreign OSes."""
    files = sorted(p for p in vendor.glob("proton-drive*") if p.is_file())
    named = [p for p in files if p.name.startswith("proton-drive-")]
    plain = [p for p in files if not p.name.startswith("proton-drive-")]
    chosen = named or plain
    if not keep_all:
        matched = [p for p in chosen if p.name.startswith(f"proton-drive-{SYSTEM}-")]
        if matched:
            chosen = matched
        elif named:
            print(f"WARNING: no CLI build for {SYSTEM}; bundling {[p.name for p in chosen]}")
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Neutron Migrator for this platform.")
    parser.add_argument("--onefile", action="store_true", help="single-file executable")
    parser.add_argument("--no-package", action="store_true", help="skip the archive step")
    parser.add_argument("--all-cli", action="store_true", help="bundle every CLI binary in vendor/")
    args = parser.parse_args()

    if importlib.util.find_spec("PyInstaller") is None:
        sys.exit("PyInstaller is not installed. Run: pip install -U pyinstaller")

    vendor = ROOT / "vendor" / "proton-drive"
    binaries = select_binaries(vendor, args.all_cli)
    if not binaries:
        sys.exit(f"No CLI binary in {vendor}. Run: python scripts/fetch_proton_cli.py")

    print(f"Target: {host_tag()}")
    for binary in binaries:
        print(f"  engine: {binary.name} ({binary.stat().st_size / 1_048_576:.1f} MiB)")

    assets = ROOT / "src" / "neutron_migrator" / "assets"
    if not assets.is_dir():
        sys.exit(f"Missing assets directory: {assets}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--onefile" if args.onefile else "--onedir",
        "--name", APP,
        "--paths", str(ROOT / "src"),
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--add-data", f"{assets}{SEP}neutron_migrator/assets",
    ]
    for binary in binaries:
        cmd += ["--add-binary", f"{binary}{SEP}."]
    for module in EXCLUDES:
        cmd += ["--exclude-module", module]

    icon_name = {"windows": "icon.ico", "darwin": "icon.icns"}.get(SYSTEM, "icon.png")
    icon = ROOT / "packaging" / "icons" / icon_name
    if icon.is_file():
        cmd += ["--icon", str(icon)]
    else:
        print(f"  note: no icon at {icon}; building with the default one")

    if sys.platform == "darwin":
        cmd += ["--osx-bundle-identifier", "me.froggywarrior.neutronmigrator"]

    cmd.append(str(ROOT / "run.py"))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(f"PyInstaller failed (exit {result.returncode}). Check the output above.")

    if args.no_package:
        print("Build finished (packaging skipped).")
        return

    dist = ROOT / "dist"
    tag = host_tag()
    if sys.platform == "win32":
        out = dist / f"NeutronMigrator-{tag}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((dist / APP).rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(dist))
    elif sys.platform == "linux":
        out = dist / f"NeutronMigrator-{tag}.tar.gz"
        with tarfile.open(out, "w:gz") as archive:
            archive.add(dist / APP, arcname=APP)
    else:
        out = dist / f"NeutronMigrator-{tag}-app.zip"
        subprocess.run(
            ["ditto", "-c", "-k", "--keepParent", str(dist / f"{APP}.app"), str(out)],
            check=True,
        )
    print(f"Artifact: {out} ({out.stat().st_size / 1_048_576:.1f} MiB)")


if __name__ == "__main__":
    main()