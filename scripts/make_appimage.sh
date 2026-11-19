#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCH="${ARCH:-$(uname -m)}"
APPDIR="$ROOT/build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ROOT/dist/Neutron Migrator" "$APPDIR/usr/bin/neutron-migrator"
cp "$ROOT/packaging/linux/neutron-migrator.desktop" "$APPDIR/usr/share/applications/"
cp "$ROOT/packaging/linux/neutron-migrator.desktop" "$APPDIR/"
cp "$ROOT/packaging/icons/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/neutron-migrator.png"
cp "$ROOT/packaging/icons/icon.png" "$APPDIR/neutron-migrator.png"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/neutron-migrator/Neutron Migrator" "$@"
EOF
chmod +x "$APPDIR/AppRun"
TOOL="$ROOT/build/appimagetool-$ARCH.AppImage"
if [ ! -x "$TOOL" ]; then
  curl -fL -o "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
  chmod +x "$TOOL"
fi
ARCH="$ARCH" "$TOOL" --appimage-extract-and-run "$APPDIR" "$ROOT/dist/NeutronMigrator-linux-$ARCH.AppImage"