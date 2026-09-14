#!/bin/bash
# Build, bundle and optionally install the Flatpak.
# Requires: flatpak-builder, uv. The SDK and runtime named in the manifest are
# installed from flathub if missing.
#
# Usage:
#   ./scripts/build-flatpak.sh              # build only
#   ./scripts/build-flatpak.sh --install    # build and install for current user
#   ./scripts/build-flatpak.sh --run        # build, install, and run

set -e

source "$(dirname "$(realpath "$0")")/common.sh"

RUNTIME="$(manifest_value runtime)"
SDK="$(manifest_value sdk)"
RUNTIME_VERSION="$(manifest_value runtime-version)"

BUILD_DIR="flatpak-build"
REPO_DIR="flatpak-repo"
REQUIREMENTS="flatpak-requirements.txt"

# ensure SDK and runtime are available
for ref in "$SDK//$RUNTIME_VERSION" "$RUNTIME//$RUNTIME_VERSION"; do
    if ! flatpak info "$ref" &>/dev/null; then
        echo "Installing $ref ..."
        flatpak install -y --user flathub "$ref"
    fi
done

# the manifest installs Python deps from uv.lock rather than keeping its own list
echo "Exporting locked Python dependencies ..."
uv export --locked --no-dev --format requirements.txt --no-emit-project \
    --prune pygobject --no-header --no-annotate --output-file "$REQUIREMENTS"

echo "Building Flatpak ..."
flatpak-builder --force-clean "$BUILD_DIR" "$MANIFEST" --repo="$REPO_DIR"

echo "Bundling Flatpak ..."
flatpak build-bundle "$REPO_DIR" "${APP_ID##*.}.flatpak" "$APP_ID"

if [[ "$1" == "--install" || "$1" == "--run" ]]; then
    echo "Installing ..."
    # point the remote at this checkout's repo even if it was added from another path
    flatpak --user remote-add --no-gpg-verify --if-not-exists \
        blenderlauncher-local "$PROJECT_DIR/$REPO_DIR"
    flatpak --user remote-modify --url="file://$PROJECT_DIR/$REPO_DIR" blenderlauncher-local
    flatpak --user install -y --reinstall blenderlauncher-local "$APP_ID"
fi

if [[ "$1" == "--run" ]]; then
    echo "Running ..."
    flatpak run "$APP_ID"
fi

echo "Done."
