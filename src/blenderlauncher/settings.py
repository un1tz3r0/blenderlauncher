import json
import pathlib


DEFAULTS = {
    "download_dir": "~/Downloads",
    "auto_cleanup": False,
    "keep_versions": 3,
    "branch_filter": "all",
    # None: auto-detect from the platform we are running on (core.detect_os)
    "filter_os": None,
}

CONFIG_DIR = pathlib.Path("~/.config/blenderlauncher").expanduser()
CONFIG_FILE = CONFIG_DIR / "settings.json"


def load():
    """Load settings from disk, falling back to defaults."""
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
