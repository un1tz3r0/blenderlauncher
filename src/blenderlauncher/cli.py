"""Command-line front-end for Blender Launcher.

This is the terminal counterpart of the GTK application in `app.py`: both are
thin shells around the same `core` routines — scrape the daily builds page,
merge the result with what is already on disk, then download / extract / launch
a build — both read their defaults from the shared `settings` file.
"""

import argparse
import asyncio
import collections
import pathlib
import shutil
import sys
import time

from . import core, settings


class ProgressPrinter:
    """Renders core's `(done, total, status)` progress callbacks on one tty line.

    The GUI feeds those callbacks into a Gtk.ProgressBar; here they become a
    throttled single-line bar with a percentage and an ETA.
    """

    def __init__(self, unit="bytes", enabled=True, interval=0.2):
        self.unit = unit
        self.enabled = enabled
        self.interval = interval
        self._start = time.monotonic()
        self._last_draw = 0.0
        self._drawn = False

    def __call__(self, done, total, status):
        if not self.enabled:
            return
        now = time.monotonic()
        finished = total > 0 and done >= total
        if not finished and now - self._last_draw < self.interval:
            return
        self._last_draw = now

        elapsed = now - self._start
        if total > 0:
            fraction = min(done / total, 1.0)
            eta = elapsed / fraction - elapsed if fraction > 0.01 else None
            detail = f"{self._amount(done)} / {self._amount(total)}"
            line = f"{status} {self._bar(fraction)} {fraction * 100:5.1f}%  {detail}  {self._eta(eta)}"
        else:
            line = f"{status} {self._amount(done)}"
        self._draw(line)

    def finish(self, message=None):
        """Clear the progress line and print a summary in its place."""
        if self._drawn:
            self._draw("")  # blank out whatever was on the line
            print("\r", end="")
        if message:
            print(message)
        self._drawn = False
        self._start = time.monotonic()
        self._last_draw = 0.0

    def _draw(self, line):
        width = max(shutil.get_terminal_size((80, 24)).columns - 1, 20)
        print(f"\r{line[:width]:<{width}}", end="", flush=True)
        self._drawn = True

    def _amount(self, value):
        if self.unit != "bytes":
            return f"{value:,} {self.unit}"
        for unit, scale in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
            if value >= scale:
                return f"{value / scale:.1f} {unit}"
        return f"{value} B"

    @staticmethod
    def _bar(fraction, width=28):
        filled = int(fraction * width)
        return "[" + "#" * filled + "-" * (width - filled) + "]"

    @staticmethod
    def _eta(eta):
        if eta is None:
            return "ETA --"
        if eta >= 60:
            return f"ETA {int(eta) // 60}m{int(eta) % 60:02d}s"
        return f"ETA {int(eta)}s"


async def gather_builds(download_dir, os_filter, branch="all", offline=False):
    """Remote + local builds, merged and sorted newest first — same pipeline the
    GUI runs in `_async_load_builds`."""
    local_builds = core.find_local_builds(download_dir, os_filter=os_filter)

    remote_builds = []
    if not offline:
        try:
            remote_builds = await core.scrape_daily_builds(os_filter=os_filter)
        except Exception as err:
            print(f"Warning: could not fetch remote builds: {err}", file=sys.stderr)

    builds = core.merge_builds(remote_builds, local_builds)
    if branch and branch != "all":
        builds = [b for b in builds if b.build_type == branch]
    if offline:
        builds = [b for b in builds if b.downloaded]
    return builds


def print_builds(builds, os_filter):
    """Numbered listing; the index of a row is the value to pass to --last."""
    if not builds:
        print(f"No {os_filter} builds found.")
        return
    print(f"Available {os_filter} builds (newest first; the index is the --last/-l value):")
    # windows/macos publish several archives per build (arch and installer
    # format), which share a display name — fall back to the filename there.
    ambiguous = collections.Counter(b.display_name for b in builds)
    for index, build in enumerate(builds):
        date = build.date.strftime("%Y-%m-%d %H:%M") if build.date else "unknown date"
        name = build.filename if ambiguous[build.display_name] > 1 else build.display_name
        print(
            f"{index:>3}: {name}"
            f"  [{build.build_type}]  {build.status_text}  ({date})"
        )


async def prepare_build(build, download_dir, allow_download=True, show_progress=True):
    """Make sure `build` is downloaded and extracted; return its extract path."""
    if not core.can_prepare_build(build):
        raise RuntimeError(core.unsupported_build_message(build))

    if not build.extracted:
        if not build.downloaded:
            if not allow_download:
                raise RuntimeError("not downloaded yet and downloading is disabled")
            if not build.download_url:
                raise RuntimeError("no download URL known for this build")

            save_dir = pathlib.Path(download_dir).expanduser().absolute()
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / build.filename

            print(f"Downloading {build.filename} -> {save_path}")
            progress = ProgressPrinter(unit="bytes", enabled=show_progress)
            build.archive_path = await core.download_build(
                build.download_url, save_path, progress, fallback_date=build.date
            )
            build.downloaded = True
            progress.finish(f"Downloaded {build.filename}")

        print(f"Extracting {pathlib.Path(build.archive_path).name}")
        progress = ProgressPrinter(unit="files", enabled=show_progress)
        build.extract_path = await core.extract_build(build.archive_path, progress)
        build.extracted = True
        progress.finish(f"Extracted to {build.extract_path}")

    return build.extract_path


def cleanup_old_builds(download_dir, keep, os_filter, protect=None):
    """Delete local builds beyond the newest `keep`, mirroring the GUI's
    auto-cleanup. `protect` is a filename that is never removed."""
    local = core.find_local_builds(download_dir, os_filter=os_filter)
    ordered = sorted(local.values(), key=lambda b: b.sort_key, reverse=True)
    for build in ordered[max(keep, 0):]:
        if protect and build.filename == protect:
            continue
        try:
            core.delete_build(build)
            print(f"Cleaned up {build.display_name}")
        except Exception as err:
            print(f"Warning: could not clean up {build.display_name}: {err}", file=sys.stderr)


async def run_blender(extract_path, build_os=None):
    """Launch Blender and wait for it, without blocking the event loop."""
    executable = core.blender_executable_path(extract_path, build_os)
    print(f"Running {executable}")
    sys.stdout.flush()  # keep our output ahead of the child's
    proc = core.launch_blender(extract_path, build_os)
    return await asyncio.to_thread(proc.wait)


def build_parser(config):
    default_os = config.get("filter_os") or core.detect_os()

    parser = argparse.ArgumentParser(
        prog="blenderlauncher-cli",
        description=(
            "Download and/or launch the latest daily build of Blender from "
            "blender.org."
        ),
    )
    parser.add_argument(
        "-d",
        "--download-dir",
        default=config["download_dir"],
        help="Download directory (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--os",
        dest="os_filter",
        default=default_os,
        choices=sorted(core.OS_ARCHIVE_SUFFIXES),
        help=(
            "Which platform's builds to consider "
            f"(default: {default_os}, detected from the running system)"
        ),
    )
    parser.add_argument(
        "-b",
        "--branch",
        default=config.get("branch_filter", "all"),
        help='Only consider this branch (stable/candidate/beta/alpha/...), or "all" (default: %(default)s)',
    )
    parser.add_argument(
        "-D",
        "--no-download",
        action="store_true",
        help="Do not download anything; only use builds already in the download directory",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Only try the selected build; do not fall back to older ones when it fails",
    )
    parser.add_argument(
        "-c",
        "--cleanup",
        action="store_true",
        help="After a successful launch, delete local builds beyond --keep",
    )
    parser.add_argument(
        "-k",
        "--keep",
        type=int,
        default=config.get("keep_versions", 3),
        help="How many local builds --cleanup keeps (default: %(default)s)",
    )
    parser.add_argument(
        "-r",
        "--no-run",
        action="store_true",
        help="Do not run Blender; just print the path to the executable that would be started",
    )
    parser.add_argument(
        "-l",
        "--last",
        type=int,
        default=0,
        help="Skip the n newest builds, e.g. when the newest one is broken (default: 0)",
    )
    parser.add_argument(
        "-s",
        "--show",
        action="store_true",
        help="Show a numbered list of builds, in the same order used by --last/-l",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    return parser


async def async_main(args):
    builds = await gather_builds(
        args.download_dir,
        os_filter=args.os_filter,
        branch=args.branch,
        offline=args.no_download,
    )

    if args.show:
        print_builds(builds, args.os_filter)
        return 0

    if not builds:
        print(
            f"No {args.os_filter} builds available"
            f"{' locally' if args.no_download else ''}.",
            file=sys.stderr,
        )
        return 1

    if args.last >= len(builds):
        print(
            f"Only {len(builds)} build(s) available; cannot skip {args.last}.",
            file=sys.stderr,
        )
        return 1

    candidates = builds[args.last:]
    if args.force:
        candidates = candidates[:1]

    show_progress = args.verbose or sys.stdout.isatty()

    for offset, build in enumerate(candidates):
        index = args.last + offset
        print(f"--- #{index}: {build.display_name} ({build.status_text}) ---")
        if args.verbose and build.download_url:
            print(f"    url: {build.download_url}")
        try:
            extract_path = await prepare_build(
                build,
                args.download_dir,
                allow_download=not args.no_download,
                show_progress=show_progress,
            )
            if args.cleanup:
                cleanup_old_builds(
                    args.download_dir,
                    args.keep,
                    args.os_filter,
                    protect=build.filename,
                )
            if args.no_run:
                print(core.blender_executable_path(extract_path, build.build_os))
                return 0

            status = await run_blender(extract_path, build.build_os)
            if status != 0:
                raise RuntimeError(f"Blender exited with status {status}")
            print("Blender exited normally.")
            return 0
        except Exception as err:
            print(f"Error: {err}", file=sys.stderr)
            if args.force:
                return 1
            print("Falling back to the next most recent build...")

    print("No usable build found.", file=sys.stderr)
    return 1


def main(argv=None):
    config = settings.load()
    args = build_parser(config).parse_args(argv)
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
