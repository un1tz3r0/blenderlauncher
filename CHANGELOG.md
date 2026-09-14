# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Consistency Tests:** `tests/test_consistency.py` (run with `uv run pytest`)
  checks that the desktop entry, AppStream metainfo, Flatpak manifest,
  `pyproject.toml` and the package agree on app id, name, summary, GUI command,
  version and the config-directory permission, and that settings defaults are
  not repeated at call sites. `pytest` and `pyyaml` are dev dependencies.
- **Installed Icon Sizes:** The pre-rendered 32–256px PNGs from `icons/` are now
  installed into the hicolor theme alongside the scalable icon.
- **Platform Detection:** `core.detect_os()` maps the running platform onto the
  builder page's OS names (`linux`/`macos`/`windows`), and both front-ends now
  use it as the default OS filter instead of assuming Linux. A `filter_os`
  setting overrides the detected value; `None` means auto-detect.
- **OS-Aware Scraping:** `scrape_daily_builds()` and `find_local_builds()` take
  an `os_filter` argument and match the archive suffixes each platform publishes
  (`.tar.xz` / `.zip`,`.msi`,`.msix` / `.dmg`).
- **CLI Options:** `--os/-o` (defaults to the detected platform), `--branch/-b`
  (branch filter, defaulting to the GUI's saved selection) and `--keep/-k`
  (how many builds `--cleanup` retains).
- **Branch Filter Dropdown:** A dropdown overlaid on the bottom of the splash banner lets users limit the list to a single branch (stable/beta/alpha/etc.) or show "All Branches". Selection is persisted in settings and the branch set is discovered dynamically from the scraped page.
- **Branch Accent Colors:** Build rows now carry a colored left strip matching the Blender website conventions — green for stable, yellow for beta, red for alpha (plus candidate/patch). A matching `.badge-stable` style was added.
- **Filename-Based Branch Inference:** Local archives found on disk now have their branch inferred from the filename instead of defaulting to "alpha", which was incorrect for most downloads.
- **Release Date Tracking:** Extracted release dates from the Blender daily builds page for more accurate sorting.
- **Persistent Date Storage:** Metadata is now saved in `.date` files next to archives and `.blenderlauncher-date` inside extracted directories to maintain sorting after restarts.
- **HTTP Header Sync:** File modification times are now set based on the `Last-Modified` HTTP header during download when available.
- **Sort Logic:** The version list now prioritizes the release date, ensuring the latest builds are always at the top regardless of download status.
- **CLI Enhancements:** Updated the `cli/blenderlatest.py` script to use the same scraping and sorting improvements as the GUI.

### Fixed
- **Stale Version:** `blenderlauncher.__version__` said 0.1.0 while the package
  was 0.2.1; it is now read from the installed package metadata.
- **XDG Directories:** Settings live in `$XDG_CONFIG_HOME/blenderlauncher`
  instead of always `~/.config` (the Flatpak keeps using the host `~/.config`
  so it still shares settings with the CLI), and the default download directory
  is the desktop's localized Downloads folder instead of `~/Downloads`.
- **Flatpak Missing lxml:** pip skipped `lxml` during the Flatpak build because
  the GNOME SDK ships its own copy, but the Platform runtime does not, so the
  installed app had no lxml parser. Dependencies are now installed with
  `--ignore-installed`, which also lets the `lxml>=6.1.0` security minimum
  build again (it previously failed trying to upgrade lxml without network).
- **Build List Never Loading:** `core.detect_os()` used `sys` without importing
  it, and `scrape_daily_builds()` named its parameter `filter_os` while every
  caller passed `os_filter`. The GUI's loader died on the background loop and the
  spinner spun forever. `scrape_daily_builds()` now takes `os_filter`, including
  an iterable of OS names.
- **Local Branch Filter:** `find_local_builds()` raised `TypeError` whenever a
  list `filter_build_type` *matched* an archive instead of keeping it.
- **Duplicate Scraped Builds:** The builder page links each archive from
  several buttons, so `scrape_daily_builds()` returned every build about three
  times. It now skips URLs it has already seen.
- **Silent Async Failures:** `AsyncBridge.run()` now prints the traceback of any
  task that raises, so a failure no longer looks like a hang.
- **Scraping Logic:** Refined the BeautifulSoup selectors to handle the current structure of the Blender daily builds page.
- **Build Sorting:** Resolved an issue where versions appeared out of order due to relying on filenames and hashes alone.
- **Auto-Cleanup Sorting:** Corrected the auto-cleanup mechanism to use the new release date sort order.

### Changed
- **Single Source of Truth:** App name and summary are `APP_NAME`/`APP_SUMMARY`
  in `blenderlauncher/__init__.py`; the GUI uses them and `APP_ID` instead of
  string literals. The CLI and GUI index `settings.load()` directly instead of
  repeating defaults, and the CLI's program name comes from its entry point.
  The desktop entry's Comment now matches the AppStream summary.
- **Shared Install Scripts:** `scripts/common.sh` holds the project-root and
  manifest-reading code used by all scripts; `scripts/install-data.sh` is the
  one list of installed desktop/metainfo/icon files, used by the Flatpak
  manifest and `install-desktop.sh`. The duplicate SVG in `data/icons` was removed;
  the scalable icon is now installed from `icons/blenderlauncher_large.svg`.
- **Flatpak Runtime:** Moved the Flatpak from the end-of-life GNOME 48 runtime
  (unsupported since 2026-03-24) to GNOME 50. `scripts/build-flatpak.sh` now
  reads the manifest, app id, runtime and SDK from the manifest instead of
  hard-coding them, and the manifest uses `${FLATPAK_ID}` for installed files.
- **Flatpak Dependencies:** The manifest no longer keeps its own list of Python
  packages; `build-flatpak.sh` exports `uv.lock` to `flatpak-requirements.txt`
  and the build installs exactly those pinned, hash-checked versions.
- **Security Updates:** Upgraded `aiohttp` 3.13.3 → 3.14.3, `lxml` 6.0.2 → 6.1.3,
  `soupsieve` 2.8.3 → 2.9.2 and `idna` 3.11 → 3.19 to clear all 28 open
  Dependabot alerts; the `aiohttp` and `lxml` minimums in `pyproject.toml` now
  exclude the vulnerable releases.
- **Project Layout:** Sources moved to `src/blenderlauncher/`, icons to `icons/`,
  and helper scripts to `scripts/`; the old `cli/blenderlatest.py` is replaced by
  the `blenderlauncher-cli` entry point.
- **README:** Added main-window and Preferences screenshots, fixed paths for the
  moved icon and scripts, and documented the girepository build dependency.
- **CLI Rewritten on `core`:** `blenderlauncher/cli.py` (moved from
  `cli/blenderlatest.py`) is now a thin front-end over the same `core` routines
  the GTK app uses — scrape, merge with local builds, download, extract, launch —
  instead of carrying its own duplicated copy of that logic, and it reads its
  defaults from the shared `settings` file. Its progress output is core's
  progress callback rendered as a terminal progress bar with an ETA.
- **CLI `--last/-l` Semantics:** the index now refers to the merged
  remote+local list that `--show/-s` prints, and no longer implies
  `--no-download`; skipped-over builds are downloaded on demand. `--cleanup`
  keeps the newest `--keep` builds (as the GUI's auto-cleanup does) rather than
  deleting every older one, and never deletes the build it just launched.
- **Archive Path Handling:** `core.archive_extract_path()` strips a known
  archive suffix instead of chopping the last two path suffixes, which was
  fragile for filenames containing dots.
- **Dynamic Branch Scraping:** `scrape_daily_builds` now discovers the branch type from each link's `plausible-event-build=<X>` class rather than iterating a hardcoded list, so new branches on the builder page appear automatically.
- **Archive Extraction:** The extraction process now copies the release date metadata into the extracted folder.
- **GUI Updates:** The build rows now display the release date alongside the status text.
- **Preferences:** Internal handling of the download directory and keep count has been made more robust.
