# TODO — Branch filtering feature

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
- [ ] smoke-test the GUI end-to-end (run the app, verify dropdown, filter, colors)
