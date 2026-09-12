#!/bin/bash
# Install desktop entry, icon, and metainfo for local (non-Flatpak) usage.
# Run this after `pip install -e .`

set -e

# Find the projects root directory by getting this script file's absolute path
# using $(realpath "$0"), and then stripping off the filename to get its 
# parent directory, which is either the project root or the scripts/ 
# subdirectory of it, in which case we get its parent directory which will be
# the projects root directory. Afterward, $PROJECT_DIR should contain the full
# path to the projects root directory.
SCRIPT_DIR="$(dirname "$(realpath "$0")")"
if [[ "$(basename "${SCRIPT_DIR}")" == "scripts" ]]; then
    PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
else
    PROJECT_DIR="${SCRIPT_DIR}"
fi

# Make sure the projects root is the working directory, or rest of this script probably won't work and 
cd "$PROJECT_DIR"


pip3 install -e . --break-system-packages

PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}"

install -Dm644 data/org.blenderlauncher.BlenderLauncher.desktop \
  "$PREFIX/applications/org.blenderlauncher.BlenderLauncher.desktop"

install -Dm644 data/icons/hicolor/scalable/apps/org.blenderlauncher.BlenderLauncher.svg \
  "$PREFIX/icons/hicolor/scalable/apps/org.blenderlauncher.BlenderLauncher.svg"

install -Dm644 data/org.blenderlauncher.BlenderLauncher.metainfo.xml \
  "$PREFIX/metainfo/org.blenderlauncher.BlenderLauncher.metainfo.xml"

# update icon cache
gtk-update-icon-cache -f -t "$PREFIX/icons/hicolor" 2>/dev/null || true

echo "Installed! You can now find 'Blender Launcher' in your app launcher."
