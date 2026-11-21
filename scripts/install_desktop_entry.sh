#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${1:-$ROOT/dist/Neutron Migrator/Neutron Migrator}"
[ -x "$BIN" ] || { echo "Usage: $0 /path/to/Neutron\\ Migrator"; exit 1; }
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$APPS" "$ICONS"
cp "$ROOT/packaging/icons/icon.png" "$ICONS/neutron-migrator.png"
sed -e "s|^Exec=.*|Exec=\"$BIN\"|" -e "s|^TryExec=.*|TryExec=$BIN|" \
    "$ROOT/packaging/linux/neutron-migrator.desktop" > "$APPS/neutron-migrator.desktop"
update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -q -t -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "Installed. Log out/in if the dock still shows a generic icon."