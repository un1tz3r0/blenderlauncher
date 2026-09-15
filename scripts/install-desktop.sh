#!/bin/bash
# Install desktop entry, icon, and metainfo for local (non-Flatpak) usage.

set -e
source "$(dirname "$(realpath "$0")")/common.sh"

PIP_INSTALL_ARGS=(-e .)
if [[ "${BLENDERLAUNCHER_BREAK_SYSTEM_PACKAGES:-0}" == "1" ]]; then
  PIP_INSTALL_ARGS+=(--break-system-packages)
fi
pip3 install "${PIP_INSTALL_ARGS[@]}"

PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}"
scripts/install-data.sh "$PREFIX"

# update icon cache
gtk-update-icon-cache -f -t "$PREFIX/icons/hicolor" 2>/dev/null || true

APP_NAME="$(sed -n 's/^Name=//p' "data/$APP_ID.desktop")"
echo "Installed! You can now find '$APP_NAME' in your app launcher."
