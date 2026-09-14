#!/bin/bash
# Install desktop entry, icon, and metainfo for local (non-Flatpak) usage.

set -e
source "$(dirname "$(realpath "$0")")/common.sh"

pip3 install -e . --break-system-packages

PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}"
scripts/install-data.sh "$PREFIX"

# update icon cache
gtk-update-icon-cache -f -t "$PREFIX/icons/hicolor" 2>/dev/null || true

APP_NAME="$(sed -n 's/^Name=//p' "data/$APP_ID.desktop")"
echo "Installed! You can now find '$APP_NAME' in your app launcher."
