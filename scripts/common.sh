# Shared helpers for the scripts in this directory; source it, don't run it.
#
# After sourcing, the working directory is the project root and these are set,
# all read from the Flatpak manifest, which is the source of truth for them:
#   PROJECT_DIR  MANIFEST  APP_ID

# the project root is the parent of this scripts/ directory
PROJECT_DIR="$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")"
cd "$PROJECT_DIR"

# the manifest is the top-level YAML file that declares an app-id
MANIFEST="$(grep -l '^app-id:' ./*.yml 2>/dev/null | head -n1)"
if [[ -z "$MANIFEST" ]]; then
    echo "No Flatpak manifest (*.yml with app-id) found in $PROJECT_DIR" >&2
    exit 1
fi

# print the scalar value of a top-level key in the manifest, unquoted
manifest_value() {
    local value
    value="$(sed -nE "s/^$1:[[:space:]]*['\"]?([^'\"]*)['\"]?[[:space:]]*$/\\1/p" "$MANIFEST")"
    if [[ -z "$value" ]]; then
        echo "Could not read '$1' from $MANIFEST" >&2
        exit 1
    fi
    echo "$value"
}

APP_ID="$(manifest_value app-id)"
