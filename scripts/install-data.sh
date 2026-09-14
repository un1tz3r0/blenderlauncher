#!/bin/bash
# Install the desktop entry, AppStream metainfo and icons into a share directory.
# Used by both the Flatpak manifest (/app/share) and install-desktop.sh
# (~/.local/share), so the list of installed files lives in one place.
#
# Usage: scripts/install-data.sh SHARE_DIR

set -e
source "$(dirname "$(realpath "$0")")/common.sh"

SHARE_DIR="${1:?usage: $0 SHARE_DIR}"

install -Dm644 "data/$APP_ID.desktop" "$SHARE_DIR/applications/$APP_ID.desktop"
install -Dm644 "data/$APP_ID.metainfo.xml" "$SHARE_DIR/metainfo/$APP_ID.metainfo.xml"

# icons/ holds the artwork and the PNG sizes mkicons.sh renders from it
ICONS="$SHARE_DIR/icons/hicolor"
install -Dm644 icons/blenderlauncher_large.svg "$ICONS/scalable/apps/$APP_ID.svg"
for png in icons/blenderlauncher_*px.png; do
    size="${png##*_}"
    size="${size%px.png}"
    install -Dm644 "$png" "$ICONS/${size}x${size}/apps/$APP_ID.png"
done
