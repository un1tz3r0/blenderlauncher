"""Blender Launcher - GTK4/Adwaita GUI for Blender daily builds."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    # running from a source tree that was never installed (PYTHONPATH=src)
    __version__ = "0+unknown"

# Identity shared by the GUI, the desktop entry, the AppStream metainfo and the
# Flatpak manifest. Those files cannot import Python, so tests/test_consistency.py
# checks that they agree with these values.
APP_ID = "org.blenderlauncher.BlenderLauncher"
APP_NAME = "Blender Launcher"
APP_SUMMARY = "Download and launch Blender daily builds"
