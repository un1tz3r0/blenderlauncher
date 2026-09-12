#!/bin/bash
# Build and optionally install the Flatpak.
# Requires: flatpak-builder, org.gnome.Sdk//48, org.gnome.Platform//48
#
# Usage:
#   ./scripts/build-flatpak.sh              # build only
#   ./scripts/build-flatpak.sh --install    # build and install for current user
#   ./scripts/build-flatpak.sh --run        # build, install, and run

set -e

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
if [[ "$(basename "${SCRIPT_DIR}")" == "scripts" ]]; then
    PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
else
    PROJECT_DIR="${SCRIPT_DIR}"
fi
cd "$PROJECT_DIR"

APP_ID="org.blenderlauncher.BlenderLauncher"
MANIFEST="$APP_ID.yml"
BUILD_DIR="flatpak-build"
REPO_DIR="flatpak-repo"

# ensure SDK and runtime are available
if ! flatpak info org.gnome.Sdk//48 &>/dev/null; then
    echo "Installing org.gnome.Sdk//48 ..."
    flatpak install -y --user flathub org.gnome.Sdk//48
fi
if ! flatpak info org.gnome.Platform//48 &>/dev/null; then
    echo "Installing org.gnome.Platform//48 ..."
    flatpak install -y --user flathub org.gnome.Platform//48
fi

echo "Building Flatpak ..."
flatpak-builder --force-clean "$BUILD_DIR" "$MANIFEST" --repo="$REPO_DIR"

if [[ "$1" == "--install" || "$1" == "--run" ]]; then
    echo "Installing ..."
    flatpak --user remote-add --no-gpg-verify --if-not-exists \
        blenderlauncher-local "$REPO_DIR"
    flatpak --user install -y --reinstall blenderlauncher-local "$APP_ID"
fi

if [[ "$1" == "--run" ]]; then
    echo "Running ..."
    flatpak run "$APP_ID"
fi

echo "Done."
