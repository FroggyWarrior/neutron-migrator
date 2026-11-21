#!/usr/bin/env bash
# Build an AppImage from the PyInstaller onedir output of scripts/build.py.
#
# Usage:
#   bash scripts/make_appimage.sh
#   ARCH=aarch64 bash scripts/make_appimage.sh
#   APPIMAGETOOL=/path/to/appimagetool bash scripts/make_appimage.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCH="${ARCH:-$(uname -m)}"
APP_NAME="Neutron Migrator"
BUNDLE="$ROOT/dist/$APP_NAME"
APPDIR="$ROOT/build/AppDir"
OUT="$ROOT/dist/NeutronMigrator-linux-${ARCH}.AppImage"
ICON="$ROOT/packaging/icons/icon.png"
DESKTOP="$ROOT/packaging/linux/neutron-migrator.desktop"
METAINFO="$ROOT/packaging/linux/neutron-migrator.appdata.xml"

# --- preflight ---------------------------------------------------------------
if [ ! -d "$BUNDLE" ]; then
  echo "ERROR: $BUNDLE not found." >&2
  echo "Run 'python scripts/build.py' first (without --onefile)." >&2
  exit 1
fi
for required in "$ICON" "$DESKTOP"; do
  if [ ! -f "$required" ]; then
    echo "ERROR: missing required file: $required" >&2
    exit 1
  fi
done

# --- AppDir layout -----------------------------------------------------------
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
         "$APPDIR/usr/share/metainfo"

cp -a "$BUNDLE" "$APPDIR/usr/bin/neutron-migrator"
cp "$DESKTOP" "$APPDIR/usr/share/applications/"
cp "$DESKTOP" "$APPDIR/"
cp "$ICON" "$APPDIR/usr/share/icons/hicolor/256x256/apps/neutron-migrator.png"
cp "$ICON" "$APPDIR/neutron-migrator.png"
ln -sf neutron-migrator.png "$APPDIR/.DirIcon"

if [ -f "$METAINFO" ]; then
  cp "$METAINFO" "$APPDIR/usr/share/metainfo/"
else
  echo "NOTE: $METAINFO not found; AppStream metadata will be missing."
fi

# Licenses travel inside the bundle; make sure they are readable.
if [ -d "$APPDIR/usr/bin/neutron-migrator/_internal/THIRD_PARTY_LICENSES" ]; then
  chmod -R a+r "$APPDIR/usr/bin/neutron-migrator/_internal/THIRD_PARTY_LICENSES"
fi

# Executable bits can be lost when building on NTFS/exFAT mounts.
chmod +x "$APPDIR/usr/bin/neutron-migrator/$APP_NAME"
find "$APPDIR/usr/bin/neutron-migrator" -type f -name 'proton-drive*' -exec chmod +x {} +

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/neutron-migrator/Neutron Migrator" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# --- appimagetool ------------------------------------------------------------
TOOL="${APPIMAGETOOL:-$ROOT/build/appimagetool-${ARCH}.AppImage}"
if [ ! -x "$TOOL" ]; then
  echo "Downloading appimagetool for ${ARCH}…"
  mkdir -p "$(dirname "$TOOL")"
  curl -fL --retry 3 -o "$TOOL" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
  chmod +x "$TOOL"
fi

# --- build -------------------------------------------------------------------
# --appimage-extract-and-run avoids needing FUSE (CI containers, restricted hosts).
ARCH="$ARCH" "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT"

chmod +x "$OUT"
echo "AppImage ready: $OUT ($(du -h "$OUT" | cut -f1))"