# Blender Launcher

A modern GTK4 and Libadwaita application for downloading, extracting, and launching Blender daily builds.

![Blender Launcher Icon](blenderlauncher_large.svg)

## Features

- **Daily Build Scraping:** Automatically fetches the latest daily builds from `builder.blender.org`.
- **Release Date Tracking:** Displays release dates and sorts versions chronologically so the latest is always at the top.
- **Download Management:** Supports downloading archives with progress bars and ETA estimation.
- **Automatic Extraction:** Handles `.tar.xz` archives and extracts them to a configurable directory.
- **Smart Cleanup:** Automatically cleans up old versions based on a user-defined keep count.
- **Native Experience:** Built with GTK4 and Libadwaita for a consistent GNOME look and feel.
- **Persistent Metadata:** Stores release dates in `.date` files to ensure sorting remains correct even after restarts or local changes.

## Installation

### Prerequisites

Ensure you have the following system dependencies installed:

- Python 3.11+
- GTK4
- Libadwaita
- `tar` (for extraction)
- `wget` (optional, used by the CLI tool)

### Running, from source, with `uv` (Recommended)

This will run **blenderlauncher** without installing anything, right from the cloned source tree (this repo).

First, clone the repo and `cd` to it:

```bash
git clone https://github.com/un1tz3r0/blenderlauncher
cd blenderlauncher
```

Then make sure your virtual environment is setup and launch the program:

```bash
uv sync
uv run blenderlauncher
```

### Installing on desktop linux distros

Use `install-desktop.sh`, it will install the python sources, icons and a `.desktop` file so that the program appears in your desktop environment's applications menu.

```bash
bash install-desktop.sh
```

### Manual Installation

```bash
pip install .
```

### Flatpak

You can build a flatpak package that can be installed with `flatpak install` using the `build-flatpak.sh` script.

```bash
bash build-flatpak.sh
```

## Usage

### GUI

Launch the graphical interface to manage your Blender builds:

```bash
blenderlauncher-gui
```

### CLI

A command-line tool is also available for quick updates and launches:

```bash
python3 cli/blenderlatest.py
```

## Configuration

Preferences can be adjusted within the GUI, including:
- Download directory
- Auto-cleanup toggle
- Number of versions to keep

## License

This project is licensed under the terms of the MIT license (or whichever license is specified in the project).
