import json
import os
import pathlib


def _contract_home(path):
    """Show paths under the home directory as `~/...`, as the settings file stores them."""
    path = pathlib.Path(path)
    try:
        return str(pathlib.Path("~") / path.relative_to(pathlib.Path.home()))
    except ValueError:
        return str(path)


def default_download_dir():
    """The user's XDG Downloads directory (localized, from user-dirs.dirs)."""
    try:
        from gi.repository import GLib

        path = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
    except (ImportError, ValueError):
        path = None
    return _contract_home(path or pathlib.Path.home() / "Downloads")


def config_dir():
    """Directory holding settings.json, named after this package.

    Normally `$XDG_CONFIG_HOME/blenderlauncher`. Inside the Flatpak,
    XDG_CONFIG_HOME is a private per-app directory, so we use the host's
    `~/.config/blenderlauncher` instead — the path the manifest's
    `--filesystem=xdg-config/blenderlauncher` permission exposes — so the GUI and
    the host CLI keep sharing one settings file.
    """
    if "FLATPAK_ID" in os.environ:
        base = pathlib.Path.home() / ".config"
    else:
        base = pathlib.Path(os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config")
    return base / __package__


DEFAULTS = {
    "download_dir": default_download_dir(),
    "auto_cleanup": False,
    "keep_versions": 3,
    "branch_filter": "all",
    # None: auto-detect from the platform we are running on (core.detect_os)
    "filter_os": None,
}

CONFIG_DIR = config_dir()
CONFIG_FILE = CONFIG_DIR / "settings.json"


def load():
    """Load settings from disk, falling back to defaults.

    Every key in `DEFAULTS` is present in the result, so callers index it
    directly rather than repeating defaults with `.get()`.
    """
    settings = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                settings.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def save(settings):
    """Save settings to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=2)
