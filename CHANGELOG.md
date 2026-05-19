# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Branch Filter Dropdown:** A dropdown overlaid on the bottom of the splash banner lets users limit the list to a single branch (stable/beta/alpha/etc.) or show "All Branches". Selection is persisted in settings and the branch set is discovered dynamically from the scraped page.
- **Branch Accent Colors:** Build rows now carry a colored left strip matching the Blender website conventions — green for stable, yellow for beta, red for alpha (plus candidate/patch). A matching `.badge-stable` style was added.
- **Filename-Based Branch Inference:** Local archives found on disk now have their branch inferred from the filename instead of defaulting to "alpha", which was incorrect for most downloads.
- **Release Date Tracking:** Extracted release dates from the Blender daily builds page for more accurate sorting.
- **Persistent Date Storage:** Metadata is now saved in `.date` files next to archives and `.blenderlauncher-date` inside extracted directories to maintain sorting after restarts.
- **HTTP Header Sync:** File modification times are now set based on the `Last-Modified` HTTP header during download when available.
- **Sort Logic:** The version list now prioritizes the release date, ensuring the latest builds are always at the top regardless of download status.
- **CLI Enhancements:** Updated the `cli/blenderlatest.py` script to use the same scraping and sorting improvements as the GUI.

### Fixed
- **Scraping Logic:** Refined the BeautifulSoup selectors to handle the current structure of the Blender daily builds page.
- **Build Sorting:** Resolved an issue where versions appeared out of order due to relying on filenames and hashes alone.
- **Auto-Cleanup Sorting:** Corrected the auto-cleanup mechanism to use the new release date sort order.

### Changed
- **Dynamic Branch Scraping:** `scrape_daily_builds` now discovers the branch type from each link's `plausible-event-build=<X>` class rather than iterating a hardcoded list, so new branches on the builder page appear automatically.
- **Archive Extraction:** The extraction process now copies the release date metadata into the extracted folder.
- **GUI Updates:** The build rows now display the release date alongside the status text.
- **Preferences:** Internal handling of the download directory and keep count has been made more robust.
