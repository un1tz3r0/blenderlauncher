import json
import os
import pathlib
import shlex


def _contract_home(path):
    """Show paths under the home directory as `~/...`, as the settings file stores them."""
    path = pathlib.Path(path)
    try:
        return str(pathlib.Path("~") / path.relative_to(pathlib.Path.home()))
    except ValueError:
        return str(path)


def _host_config_home():
    """The host config directory, even when the app runs inside the Flatpak."""
    if "FLATPAK_ID" in os.environ:
        return pathlib.Path.home() / ".config"
    return pathlib.Path(os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config")


def _user_dirs_download_dir():
    """Read XDG_DOWNLOAD_DIR from user-dirs.dirs when it is available."""
    user_dirs = _host_config_home() / "user-dirs.dirs"
    try:
        lines = user_dirs.read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        if line.startswith("XDG_DOWNLOAD_DIR="):
            try:
                values = shlex.split(line.split("=", 1)[1])
            except ValueError:
                return None
            return os.path.expandvars(values[0]) if values else None
    return None


def default_download_dir():
    """The user's XDG Downloads directory (localized, from user-dirs.dirs)."""
    path = _user_dirs_download_dir()
    if path is None and "FLATPAK_ID" not in os.environ:
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
    return _host_config_home() / __package__


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
