# TODO

## Branch filtering feature

- [x] core: add `infer_build_type_from_filename()` helper
- [x] core: use it in `find_local_builds` so locals aren't defaulted to "alpha"
- [x] core: make `scrape_daily_builds` discover branches dynamically from row classes
- [x] settings: add `branch_filter` default `"all"`
- [x] app: overlay filter bar (label + MenuButton) on splash bottom
- [x] app: stateful `branch-filter` action with Gio.Menu sections (All / per-branch)
- [x] app: dynamic menu rebuild from scraped branch set
- [x] app: cache unfiltered builds and filter in `_populate_list`
- [x] app: apply `branch-accent-<type>` CSS class to BuildRow
- [x] css: accent borders (stable green / beta yellow / alpha red) + `.badge-stable`
- [x] CHANGELOG.md entry
- [x] smoke-test the GUI end-to-end (run the app, verify dropdown, filter, colors)

## CLI refactor onto core

- [x] core: `detect_os()` + `OS_ARCHIVE_SUFFIXES`, `os_filter` on
      `scrape_daily_builds()` / `find_local_builds()`
- [x] core: `archive_extract_path()` / `strip_archive_suffix()` helpers
- [x] settings: `filter_os` default (`None` = auto-detect)
- [x] app: pass the configured/detected `os_filter` when loading builds
- [x] cli: rewrite as a front-end over `core` + `settings` (no duplicated scrape,
      download, extract, launch or cleanup logic)
- [x] pyproject: point `setuptools.packages.find` at the `src/` layout
- [x] delete the superseded `cli/blenderlatest.py` copy
- [ ] non-Linux support: `extract_build()` only handles `.tar.xz`, so
      `--os windows|macos` can list and download but not extract/launch
- [ ] arch filter (`x86_64` vs `arm64`) — windows/macos publish several
      archives per build, currently disambiguated only in `--show` output
