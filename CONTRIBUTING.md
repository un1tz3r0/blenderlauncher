# Contributing to Blender Launcher

Thank you for your interest in contributing to the Blender Launcher!

## How to Contribute

1.  **Report Bugs:** Use the issue tracker to report bugs. Provide as much detail as possible, including screenshots and steps to reproduce.
2.  **Suggest Features:** Share your ideas for new features or improvements.
3.  **Submit Pull Requests:** We welcome code contributions! Please follow the existing coding style and ensure your changes are well-tested.

## Development Environment

To set up a local development environment:

1.  Install `uv` (recommended).
2.  Run `uv sync` to install dependencies.
3.  Launch the application using `uv run blenderlauncher-gui`.
4.  Run the tests with `uv run pytest`.

## Single Source of Truth

Each value should be defined in one place and derived everywhere else:

- **Version:** `pyproject.toml` (`blenderlauncher.__version__` reads the installed metadata).
- **Python dependencies:** `pyproject.toml` / `uv.lock` (the Flatpak build exports the lockfile).
- **App ID, runtime and SDK:** the Flatpak manifest (the scripts read it via `scripts/common.sh`).
- **Installed desktop files and icons:** `scripts/install-data.sh`, used by both the manifest and `install-desktop.sh`.
- **Settings defaults:** `settings.DEFAULTS`; `settings.load()` fills in every key, so don't repeat defaults with `.get()`.

Some files can't import Python, such as the `.desktop` entry, the AppStream metainfo and the manifest. They repeat the app ID, name, summary and GUI command, and `tests/test_consistency.py` fails if these copies disagree with `blenderlauncher.APP_ID`, `APP_NAME`, `APP_SUMMARY` or `pyproject.toml`.

## Coding Standards

- Follow PEP 8 for Python code.
- Use descriptive variable and function names.
- Keep functions and classes focused and maintainable.
- Document any new features or significant changes.
