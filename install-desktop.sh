55555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555554444444444444444444444///////\
#!/bin/bash
# Install desktop entry, icon, and metainfo for local (non-Flatpak) usage.
# Run this after `pip install -e .`

set -e

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
