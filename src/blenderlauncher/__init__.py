"""Blender Launcher - GTK4/Adwaita GUI for Blender daily builds."""

__version__ = "0.2.1"
# Identity shared by the GUI, the desktop entry, the AppStream metainfo and the
# Flatpak manifest. Those files cannot import Python, so tests/test_consistency.py
# checks that they agree with these values.
APP_ID = "org.blenderlauncher.BlenderLauncher"
APP_NAME = "Blender Launcher"
APP_SUMMARY = "Download and launch Blender daily builds"
