import asyncio
import datetime
import pathlib
import threading
import time
import traceback

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk, Pango, Gdk

from . import APP_ID, core, settings

STYLE_CSS = pathlib.Path(__file__).parent / "style.css"

# Canonical display order for known branches; unknown branches are appended alphabetically.
_BRANCH_ORDER = ["stable", "candidate", "beta", "alpha", "patch"]


def _sort_branches(branches):
    known = [b for b in _BRANCH_ORDER if b in branches]
    extra = sorted(b for b in branches if b not in _BRANCH_ORDER)
    return known + extra


def load_css():
    """Load the custom CSS stylesheet."""
    if STYLE_CSS.exists():
        provider = Gtk.CssProvider()
        provider.load_from_path(str(STYLE_CSS))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


class AsyncBridge:
    """Runs an asyncio event loop in a background thread for non-blocking IO."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro):
        """Submit a coroutine, returns a concurrent.futures.Future.

        Callers mostly fire-and-forget, so any uncaught exception is printed here
        rather than vanishing silently inside the unobserved future."""
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        future.add_done_callback(self._report_exception)
        return future

    @staticmethod
    def _report_exception(future):
        if future.cancelled() or future.exception() is None:
            return
        exc = future.exception()
        traceback.print_exception(type(exc), exc, exc.__traceback__)


class BuildRow(Gtk.Box):
    """A row widget representing a single Blender build."""

    def __init__(self, build, on_action, on_delete):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.build = build
        self._on_action = on_action
        self._on_delete = on_delete
        self._start_time = None

        self.add_css_class("card")
        self.add_css_class("build-row")
        if build.build_type:
            self.add_css_class(f"branch-accent-{build.build_type}")
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        # --- top row: info + buttons ---
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top.set_margin_start(12)
        top.set_margin_end(12)
        top.set_margin_top(8)
        top.set_margin_bottom(4)
        self.append(top)

        # status icon
        self.status_icon = Gtk.Image()
        self._update_status_icon()
        top.append(self.status_icon)

        # labels
        labels_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels_box.set_hexpand(True)
        top.append(labels_box)

        self.name_label = Gtk.Label(label=build.display_name, xalign=0)
        self.name_label.add_css_class("heading")
        self.name_label.add_css_class("build-name")
        self.name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        labels_box.append(self.name_label)

        subtitle = build.status_text
        if build.date:
            subtitle += f" \u2014 {build.date.strftime('%Y-%m-%d %H:%M')}"
        self.subtitle_label = Gtk.Label(label=subtitle, xalign=0)
        self.subtitle_label.add_css_class("dim-label")
        self.subtitle_label.add_css_class("caption")
        labels_box.append(self.subtitle_label)

        # build type badge
        if build.build_type:
            badge = Gtk.Label(label=build.build_type.upper())
            badge.add_css_class(f"badge-{build.build_type}")
            top.append(badge)

        # action button
        self.action_button = Gtk.Button()
        self.action_button.add_css_class("suggested-action")
        self.action_button.set_valign(Gtk.Align.CENTER)
        self._update_action_button()
        self.action_button.connect("clicked", self._on_action_clicked)
        top.append(self.action_button)

        # delete button
        self.delete_button = Gtk.Button(icon_name="user-trash-symbolic")
        self.delete_button.add_css_class("flat")
        self.delete_button.add_css_class("error")
        self.delete_button.set_valign(Gtk.Align.CENTER)
        self.delete_button.set_tooltip_text("Delete this build")
        self.delete_button.set_visible(build.downloaded)
        self.delete_button.connect("clicked", self._on_delete_clicked)
        top.append(self.delete_button)

        # --- progress area (hidden by default) ---
        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.progress_box.set_margin_start(12)
        self.progress_box.set_margin_end(12)
        self.progress_box.set_margin_bottom(8)
        self.progress_box.set_visible(False)
        self.append(self.progress_box)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        self.progress_box.append(self.progress_bar)

        self.progress_label = Gtk.Label(xalign=0)
        self.progress_label.add_css_class("caption")
        self.progress_label.add_css_class("dim-label")
        self.progress_label.add_css_class("progress-detail")
        self.progress_box.append(self.progress_label)

    def _update_status_icon(self):
        # clear old status classes
        for cls in ["status-ready", "status-downloaded", "status-remote"]:
            self.status_icon.remove_css_class(cls)
        if self.build.extracted:
            self.status_icon.set_from_icon_name("emblem-ok-symbolic")
            self.status_icon.add_css_class("status-ready")
        elif self.build.downloaded:
            self.status_icon.set_from_icon_name("folder-download-symbolic")
            self.status_icon.add_css_class("status-downloaded")
        else:
            self.status_icon.set_from_icon_name("network-server-symbolic")
            self.status_icon.add_css_class("status-remote")

    def _update_action_button(self):
        if not core.can_prepare_build(self.build):
            self.action_button.set_label("Unsupported")
            self.action_button.set_icon_name("dialog-warning-symbolic")
            self.action_button.set_tooltip_text(core.unsupported_build_message(self.build))
            self.action_button.set_sensitive(False)
        elif self.build.extracted:
            self.action_button.set_label("Launch")
            self.action_button.set_icon_name("media-playback-start-symbolic")
            self.action_button.set_tooltip_text(None)
            self.action_button.set_sensitive(True)
        elif self.build.downloaded:
            self.action_button.set_label("Extract & Launch")
            self.action_button.set_icon_name("package-x-generic-symbolic")
            self.action_button.set_tooltip_text(None)
            self.action_button.set_sensitive(True)
        else:
            self.action_button.set_label("Download")
            self.action_button.set_icon_name("folder-download-symbolic")
            self.action_button.set_tooltip_text(None)
            self.action_button.set_sensitive(True)

    def _on_action_clicked(self, button):
        self._on_action(self)

    def _on_delete_clicked(self, button):
        self._on_delete(self)

    def show_progress(self, fraction, text, detail=""):
        """Update the progress display. Call from the main thread via GLib.idle_add."""
        self.progress_box.set_visible(True)
        self.action_button.set_sensitive(False)
        self.delete_button.set_sensitive(False)
        self.add_css_class("active-download")
        if fraction >= 0:
            self.progress_bar.set_fraction(min(fraction, 1.0))
        else:
            self.progress_bar.pulse()
        self.progress_bar.set_text(text)
        self.progress_label.set_label(detail)

    def hide_progress(self):
        self.progress_box.set_visible(False)
        self._update_action_button()
        self.delete_button.set_sensitive(True)
        self.remove_css_class("active-download")

    def refresh(self):
        """Update all display elements to match current build state."""
        self._update_status_icon()
        self._update_action_button()
        subtitle = self.build.status_text
        if self.build.date:
            subtitle += f" \u2014 {self.build.date.strftime('%Y-%m-%d %H:%M')}"
        self.subtitle_label.set_label(subtitle)
        self.delete_button.set_visible(self.build.downloaded)
        self.hide_progress()


class PreferencesDialog(Adw.PreferencesWindow):
    """Settings dialog for download directory, auto-cleanup, and keep count."""

    def __init__(self, current_settings, on_save, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Preferences")
        self.set_default_size(450, 650)
        self._settings = dict(current_settings)
        self._on_save = on_save

        page = Adw.PreferencesPage()
        self.add(page)

        # --- Download group ---
        dl_group = Adw.PreferencesGroup(title="Downloads")
        page.add(dl_group)

        self.dir_row = Adw.EntryRow(title="Download directory")
        self.dir_row.set_text(self._settings["download_dir"])
        dl_group.add(self.dir_row)

        # --- Cleanup group ---
        cleanup_group = Adw.PreferencesGroup(title="Cleanup")
        page.add(cleanup_group)

        self.auto_cleanup_row = Adw.SwitchRow(
            title="Auto-cleanup old versions",
            subtitle="Automatically remove old builds when newer ones are downloaded",
        )
        self.auto_cleanup_row.set_active(self._settings["auto_cleanup"])
        cleanup_group.add(self.auto_cleanup_row)

        self.keep_row = Adw.SpinRow.new_with_range(1, 20, 1)
        self.keep_row.set_title("Keep versions")
        self.keep_row.set_subtitle("Number of recent versions to keep")
        self.keep_row.set_value(self._settings["keep_versions"])
        cleanup_group.add(self.keep_row)

        # save button in the header
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save_clicked)
        # Adw.PreferencesWindow doesn't expose its headerbar directly,
        # so we use a bottom action row instead
        save_group = Adw.PreferencesGroup()
        page.add(save_group)
        save_row = Adw.ActionRow(title="Apply changes")
        save_row.add_suffix(save_btn)
        save_row.set_activatable_widget(save_btn)
        save_group.add(save_row)

    def _on_save_clicked(self, button):
        self._settings["download_dir"] = self.dir_row.get_text()
        self._settings["auto_cleanup"] = self.auto_cleanup_row.get_active()
        self._settings["keep_versions"] = int(self.keep_row.get_value())
        self._on_save(self._settings)
        self.close()


class BlenderLauncherWindow(Adw.ApplicationWindow):
    """Main application window."""

    def __init__(self, app, bridge):
        super().__init__(application=app)
        self.bridge = bridge
        self.config = settings.load()
        self.set_title("Blender Launcher")
        self.set_default_size(700, 600)

        # toast overlay wraps everything for notifications
        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        # main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._toast_overlay.set_child(main_box)

        # header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # refresh button
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_accessible_name("Refresh build list")
        refresh_btn.set_tooltip_text("Refresh build list")
        refresh_btn.connect("clicked", self._on_refresh)
        header.pack_start(refresh_btn)

        # preferences button
        prefs_btn = Gtk.Button(icon_name="emblem-system-symbolic")
        prefs_btn.set_accessible_name("Preferences")
        prefs_btn.set_tooltip_text("Preferences")
        prefs_btn.connect("clicked", self._on_prefs)
        header.pack_end(prefs_btn)

        # banner / splash area with an overlaid branch filter bar along its bottom
        self.banner = Adw.StatusPage()
        self.banner.set_icon_name("org.blenderlauncher.BlenderLauncher")
        self.banner.set_title("Blender Launcher")
        self.banner.set_description("Download and launch Blender daily builds")
        self.banner.set_vexpand(False)
        self.banner.set_valign(Gtk.Align.START)
        self.banner.add_css_class("splash-banner")

        splash_overlay = Gtk.Overlay()
        splash_overlay.set_child(self.banner)
        main_box.append(splash_overlay)

        # branch filter: stateful window action drives a radio menu
        self._filter_action = Gio.SimpleAction.new_stateful(
            "branch-filter",
            GLib.VariantType.new("s"),
            GLib.Variant.new_string(self.config.get("branch_filter", "all")),
        )
        self._filter_action.connect("change-state", self._on_branch_filter_changed)
        self.add_action(self._filter_action)

        filter_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        filter_bar.set_valign(Gtk.Align.END)
        filter_bar.set_halign(Gtk.Align.CENTER)
        filter_bar.set_margin_bottom(10)
        filter_bar.add_css_class("branch-filter-bar")
        filter_bar.append(Gtk.Label(label="Branch:"))
        self._filter_button = Gtk.MenuButton()
        self._filter_button.add_css_class("flat")
        self._filter_button.set_always_show_arrow(True)
        filter_bar.append(self._filter_button)
        splash_overlay.add_overlay(filter_bar)

        # known branches grow as the scraper discovers them; seed with the three common ones
        self._known_branches = {"stable", "beta", "alpha"}
        self._rebuild_branch_menu()

        # separator
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # scrollable build list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        main_box.append(scrolled)

        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.list_box.add_css_class("build-list")
        self.list_box.set_margin_top(8)
        self.list_box.set_margin_bottom(8)
        scrolled.set_child(self.list_box)

        # spinner shown during loading
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(32, 32)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_margin_top(24)
        self.list_box.append(self.spinner)

        self._build_rows = []
        self._all_builds = []
        self._load_builds()

    def _load_builds(self):
        """Fetch remote + local builds and populate the list."""
        self.spinner.start()
        self.spinner.set_visible(True)
        self.bridge.run(self._async_load_builds())

    async def _async_load_builds(self):
        download_dir = self.config["download_dir"]
        os_filter = self.config.get("filter_os") or core.detect_os()

        # get local builds (fast, synchronous)
        local_builds = core.find_local_builds(download_dir, os_filter=os_filter)

        # try to get remote builds
        try:
            remote_builds = await core.scrape_daily_builds(os_filter=os_filter)
        except Exception as e:
            remote_builds = []
            GLib.idle_add(self._show_toast, f"Could not fetch remote builds: {e}")

        merged = core.merge_builds(remote_builds, local_builds)
        GLib.idle_add(self._on_builds_loaded, merged)

    def _on_builds_loaded(self, builds):
        """Cache the full build list, refresh the branch menu, then render."""
        self._all_builds = builds
        discovered = {b.build_type for b in builds if b.build_type and b.build_type != "unknown"}
        if not discovered.issubset(self._known_branches):
            self._known_branches |= discovered
            self._rebuild_branch_menu()
        self._populate_list()

    def _populate_list(self):
        """Render the cached build list, filtered by the current branch selection."""
        self.spinner.stop()
        self.spinner.set_visible(False)

        # clear existing rows
        for row in self._build_rows:
            self.list_box.remove(row)
        self._build_rows.clear()

        selected = self.config.get("branch_filter", "all")
        if selected == "all":
            visible = list(self._all_builds)
        else:
            visible = [b for b in self._all_builds if b.build_type == selected]

        if not visible:
            if not self._all_builds:
                msg = "No builds found. Check your internet connection."
            else:
                msg = f"No {selected} builds available."
            empty = Gtk.Label(label=msg)
            empty.add_css_class("dim-label")
            empty.set_margin_top(24)
            self.list_box.append(empty)
            self._build_rows.append(empty)
            return

        for build in visible:
            row = BuildRow(build, self._on_build_action, self._on_build_delete)
            self.list_box.append(row)
            self._build_rows.append(row)

    def _rebuild_branch_menu(self):
        """Rebuild the branch filter dropdown menu from `self._known_branches`."""
        menu = Gio.Menu()

        all_section = Gio.Menu()
        all_section.append("All Branches", "win.branch-filter::all")
        menu.append_section(None, all_section)

        branch_section = Gio.Menu()
        for branch in _sort_branches(self._known_branches):
            branch_section.append(branch.capitalize(), f"win.branch-filter::{branch}")
        menu.append_section(None, branch_section)

        self._filter_button.set_menu_model(menu)
        self._update_filter_button_label()

    def _update_filter_button_label(self):
        selected = self.config.get("branch_filter", "all")
        label = "All Branches" if selected == "all" else selected.capitalize()
        self._filter_button.set_label(label)

    def _on_branch_filter_changed(self, action, value):
        action.set_state(value)
        selected = value.get_string()
        self.config["branch_filter"] = selected
        settings.save(self.config)
        self._update_filter_button_label()
        self._populate_list()

    def _on_build_action(self, row):
        """Handle click on a build's action button."""
        build = row.build
        if not core.can_prepare_build(build):
            self._show_toast(core.unsupported_build_message(build))
            return
        if build.extracted:
            self._launch_build(row)
        elif build.downloaded:
            self._extract_and_launch(row)
        elif build.download_url:
            self._download_extract_launch(row)

    def _on_build_delete(self, row):
        """Handle click on a build's delete button."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Delete Build?",
            body=f"Delete {row.build.display_name}? This removes the archive and extracted files.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_delete_confirmed, row)
        dialog.present()

    def _on_delete_confirmed(self, dialog, response, row):
        if response == "delete":
            try:
                core.delete_build(row.build)
                self.list_box.remove(row)
                self._build_rows.remove(row)
                self._show_toast(f"Deleted {row.build.display_name}")
                self._load_builds()
            except Exception as e:
                self._show_toast(f"Error deleting: {e}")

    def _launch_build(self, row):
        """Launch an already-extracted build."""
        try:
            proc = core.launch_blender(row.build.extract_path, row.build.build_os)
            row.hide_progress()
            self._show_toast(f"Blender launched (PID {proc.pid})")
            # monitor exit natively through the GLib main loop
            GLib.child_watch_add(
                GLib.PRIORITY_DEFAULT, proc.pid, self._on_blender_exit
            )
        except Exception as e:
            row.hide_progress()
            self._show_toast(f"Launch failed: {e}")

    def _on_blender_exit(self, pid, status):
        """Called by GLib when a launched Blender process exits."""
        import os

        try:
            exit_code = os.waitstatus_to_exitcode(status)
        except (AttributeError, ValueError):
            exit_code = status

        if exit_code < 0:
            self._show_toast(f"Blender (PID {pid}) terminated by signal {-exit_code}")
        elif exit_code != 0:
            self._show_toast(f"Blender (PID {pid}) exited with code {exit_code}")
        else:
            self._show_toast("Blender exited normally")

    def _extract_and_launch(self, row):
        """Extract a downloaded archive then launch it."""
        start_time = time.monotonic()

        def progress_cb(done, total, status):
            if total > 0:
                frac = done / total
                elapsed = time.monotonic() - start_time
                if frac > 0:
                    eta = elapsed / frac - elapsed
                    eta_str = f"ETA {int(eta)}s"
                else:
                    eta_str = ""
                detail = f"{done:,} / {total:,} files  {eta_str}"
            else:
                frac = -1
                detail = status
            GLib.idle_add(row.show_progress, frac, status, detail)

        async def _run():
            try:
                extract_path = await core.extract_build(
                    row.build.archive_path, progress_cb
                )
                row.build.extracted = True
                row.build.extract_path = extract_path
                GLib.idle_add(row.refresh)
                self._auto_cleanup_if_needed()
                # now launch
                GLib.idle_add(self._launch_build, row)
            except Exception as e:
                GLib.idle_add(row.hide_progress)
                GLib.idle_add(self._show_toast, f"Extraction failed: {e}")

        self.bridge.run(_run())

    def _download_extract_launch(self, row):
        """Download, extract, and launch a remote build."""
        download_dir = pathlib.Path(self.config["download_dir"]).expanduser().absolute()
        save_path = download_dir / row.build.filename
        start_time = time.monotonic()

        def progress_cb(done, total, status):
            if total > 0:
                frac = done / total
                elapsed = time.monotonic() - start_time
                if frac > 0.01:
                    eta = elapsed / frac - elapsed
                    eta_str = f"ETA {int(eta)}s"
                else:
                    eta_str = "calculating..."
                done_mb = done / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                detail = f"{done_mb:.1f} / {total_mb:.1f} MB  {eta_str}"
            else:
                frac = -1
                detail = status
            GLib.idle_add(row.show_progress, frac, status, detail)

        async def _run():
            try:
                path = await core.download_build(
                    row.build.download_url, save_path, progress_cb,
                    fallback_date=row.build.date
                )
                row.build.archive_path = path
                row.build.downloaded = True
                # Use actual file mtime as date if possible
                try:
                    row.build.date = datetime.datetime.fromtimestamp(path.stat().st_mtime)
                except Exception:
                    if not row.build.date:
                        row.build.date = datetime.datetime.now()

                GLib.idle_add(row.refresh)
                # proceed to extract
                GLib.idle_add(self._extract_and_launch, row)
            except Exception as e:
                GLib.idle_add(row.hide_progress)
                GLib.idle_add(self._show_toast, f"Download failed: {e}")

        self.bridge.run(_run())

    def _auto_cleanup_if_needed(self):
        """If auto-cleanup is enabled, remove old builds beyond the keep count."""
        if not self.config["auto_cleanup"]:
            return
        keep = self.config["keep_versions"]
        # get current local builds sorted newest first
        local = core.find_local_builds(
            self.config["download_dir"],
            os_filter=self.config.get("filter_os") or core.detect_os(),
        )
        sorted_builds = sorted(
            local.values(), key=lambda b: b.sort_key, reverse=True
        )
        to_remove = sorted_builds[keep:]
        for build in to_remove:
            try:
                core.delete_build(build)
                GLib.idle_add(
                    self._show_toast,
                    f"Auto-cleaned {build.display_name}",
                )
            except Exception:
                pass
        if to_remove:
            # refresh the list
            GLib.idle_add(self._load_builds)

    def _on_refresh(self, button):
        self._load_builds()

    def _on_prefs(self, button):
        dialog = PreferencesDialog(
            self.config,
            self._on_settings_saved,
            transient_for=self,
        )
        dialog.present()

    def _on_settings_saved(self, new_settings):
        self.config = new_settings
        settings.save(new_settings)
        self._show_toast("Settings saved")
        self._load_builds()

    def _show_toast(self, message):
        """Show a toast notification. Must be called on the main thread."""
        toast = Adw.Toast(title=message)
        toast.set_timeout(3)
        self._toast_overlay.add_toast(toast)


class BlenderLauncherApp(Adw.Application):
    """Main application class."""

    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.bridge = AsyncBridge()

    def do_activate(self):
        load_css()
        win = self.get_active_window()
        if not win:
            win = BlenderLauncherWindow(self, self.bridge)
        win.present()
