import asyncio
import datetime
import pathlib
import re
import shutil
import sys
from builtins import str as String
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from os import PathLike

import aiofiles
import aiohttp
import yarl
from bs4 import BeautifulSoup


class BlenderBuildType(Enum):
    STABLE = "stable"
    ALPHA = "alpha"
    BETA = "beta"
    CANDIDATE = "candidate"
    UNKNOWN = "unknown"
    @classmethod
    def from_string(cls, s: str):
      if s in cls._value2member_map_:
        return cls._value2member_map_[s]
      else:
        return cls.UNKNOWN
    def __str__(self):
        return self.value


# The builder page tags every download link with a `plausible-event-os=<name>`
# class; these are the names it uses, mapped to the archive suffixes each one
# ships. Only the linux tarballs can be extracted by `extract_build()` so far.
OS_ARCHIVE_SUFFIXES = {
    "linux": (".tar.xz",),
    "windows": (".zip", ".msi", ".msix"),
    "macos": (".dmg",),
}

EXTRACTABLE_SUFFIXES = (".tar.xz",)

_PLATFORM_SUFFIX_RE = re.compile(
    r"-(?:linux|windows|darwin|macos)(?:64)?(?:[.\-][\w.\-]*)?$"
)
_PLATFORM_TOKEN_RE = re.compile(r"(?:^|[.\-])(linux|windows|darwin|macos)(?:64)?(?:[.\-]|$)")


def detect_os(default="linux"):
    """Return the builder page's OS name for the platform we are running on.

    Falls back to `default` on platforms the builder does not publish for, so
    callers always get a usable filter value."""
    platform = sys.platform
    if platform.startswith("linux"):
        return "linux"
    if platform == "darwin":
        return "macos"
    if platform.startswith("win") or platform == "cygwin":
        return "windows"
    return default


def archive_suffixes_for_os(os_filter):
    """Archive suffixes published for the given OS name."""
    return OS_ARCHIVE_SUFFIXES.get(os_filter, OS_ARCHIVE_SUFFIXES["linux"])


def archive_suffixes_for_filter(os_filter):
    """Archive suffixes for one OS name or an iterable of OS names."""
    if isinstance(os_filter, String):
        return archive_suffixes_for_os(os_filter)
    if isinstance(os_filter, Iterable) and all(isinstance(s, String) for s in os_filter):
        return tuple(s for name in os_filter for s in archive_suffixes_for_os(name))
    raise TypeError("os_filter must be either None, a string, or an iterable of strings!")


def infer_build_os_from_filename(filename):
    """Best-effort OS detection from a Blender archive filename."""
    stem = strip_archive_suffix(filename).lower()
    match = _PLATFORM_TOKEN_RE.search(stem)
    if match:
        build_os = match.group(1)
        return "macos" if build_os == "darwin" else build_os
    for build_os, suffixes in OS_ARCHIVE_SUFFIXES.items():
        if filename.endswith(suffixes):
            return build_os
    return None


def strip_archive_suffix(filename):
    """Drop a known archive suffix (`.tar.xz`, `.zip`, `.dmg`, ...) from a name."""
    for suffixes in OS_ARCHIVE_SUFFIXES.values():
        for suffix in suffixes:
            if filename.endswith(suffix):
                return filename[: -len(suffix)]
    return filename


def archive_extract_path(archive_path):
    """The directory an archive expands into, next to the archive itself."""
    archive_path = pathlib.Path(archive_path)
    return archive_path.with_name(strip_archive_suffix(archive_path.name))


@dataclass
class BlenderBuild:
    """Represents a Blender daily build, either remote or local or both."""

    filename: String
    download_url: String | None = None
    archive_path: PathLike | None = None
    extract_path: PathLike | None = None
    build_type: String = "unknown"
    build_os: String | None = None
    downloaded: bool = False
    extracted: bool = False
    date: datetime.datetime | None = None

    @property
    def display_name(self):
        # strip extension and platform/arch tag to get a clean version string
        return _PLATFORM_SUFFIX_RE.sub("", strip_archive_suffix(self.filename))

    @property
    def status_text(self):
        if self.extracted:
            return "Ready to launch"
        elif self.downloaded:
            return "Downloaded (not extracted)"
        else:
            return "Available for download"

    @property
    def sort_key(self):
        """Newest first: prioritize date (as timestamp to handle naive/aware), then filename."""
        ts = 0
        if self.date:
            try:
                ts = self.date.timestamp()
            except (OSError, ValueError, OverflowError):
                ts = 0
        return (ts, self.filename)


def effective_build_os(build):
    """Return the known OS for a build, falling back to its filename."""
    return build.build_os or infer_build_os_from_filename(build.filename)


def can_prepare_build(build):
    """Whether this build can be downloaded/extracted/launched end-to-end."""
    return effective_build_os(build) == "linux"


def unsupported_build_message(build):
    build_os = effective_build_os(build) or "This"
    return (
        f"{build_os.capitalize()} builds can be listed, but only Linux .tar.xz builds "
        "can be prepared and launched right now."
    )


# callback signature: (bytes_done, bytes_total, status_text) -> None
ProgressCallback = Callable[[int, int, str], None]


_BUILD_TYPE_RE = re.compile(r"blender-[\d.]+-([a-z]+)")


def infer_build_type_from_filename(filename: str) -> str:
    """Extract the branch type (stable/alpha/beta/candidate/...) from a Blender
    archive filename like ``blender-4.5.0-stable+v45.abc-linux...tar.xz``."""
    match = _BUILD_TYPE_RE.match(filename)
    if match:
        return match.group(1)
    return "unknown"


async def scrape_daily_builds(os_filter=None, filter_build_type=None):
    """Scrape the Blender daily builds page and return available builds.

    `os_filter` is one of the keys of `OS_ARCHIVE_SUFFIXES` (or an iterable of
    them); it defaults to the OS we are running on."""
    if os_filter is None:
        os_filter = detect_os()
    suffixes = archive_suffixes_for_filter(os_filter)

    async with aiohttp.ClientSession() as session:
        async with session.get("https://builder.blender.org/download/daily/") as resp:
            if resp.status != 200:
                raise RuntimeError(f"Failed to fetch daily builds page: HTTP {resp.status}")
            html_text = await resp.text()

    html = BeautifulSoup(html_text, features="lxml")
    builds = []
    # each row links the same archive from several buttons; keep the first
    seen_urls = set()

    rows = html.select("li.t-row.build")
    for row in rows:
        # Extract date once per row
        date_cell = row.find("div", class_="b-date")
        build_date = None
        build_os = None

        if date_cell and "title" in date_cell.attrs:
            try:
                build_date = datetime.datetime.fromisoformat(date_cell.attrs["title"])
            except ValueError:
                build_date = None

        for a in row.find_all("a"):
            cls = a.get("class", [])
            if "plausible-event-name=Downloads+Blender" not in cls:
                continue
            url_str = a.attrs.get("href", "")
            if not url_str.endswith(suffixes) or url_str in seen_urls:
                continue

            # Discover the branch dynamically from the plausible-event-build=<X> class
            build_type = None
            for c in cls:
                if c.startswith("plausible-event-build="):
                    build_type = c.split("=", 1)[1]
                    break
            if not build_type:
                continue

            # Discover the target OS from plausible-event-os=<X> class
            build_os = None
            for c in cls:
                if c.startswith("plausible-event-os="):
                    build_os = c.split("=", 1)[1]
                    break
            if build_os == None:
                continue

            url = yarl.URL(url_str)
            filename = url.parts[-1]

            # filter by os and build type
            if os_filter != None:
                if isinstance(os_filter, String):
                    if build_os != os_filter:
                        continue
                elif isinstance(os_filter, Iterable) and all(isinstance(s, String) for s in os_filter):
                    if not any(build_os == s for s in os_filter):
                        continue
                else:
                    raise TypeError("os_filter must be either None, a string, or an iterable of strings!")

            if filter_build_type != None:
                if isinstance(filter_build_type, String):
                    if build_type != filter_build_type:
                        continue
                elif isinstance(filter_build_type, Iterable) and all(isinstance(s, String) for s in filter_build_type):
                    if not any(build_type == s for s in filter_build_type):
                        continue
                else:
                    raise TypeError("filter_type must be either None, a string, or an iterable of strings!")

            seen_urls.add(url_str)
            builds.append(
                BlenderBuild(
                    filename=filename,
                    download_url=str(url),
                    build_type=build_type,
                    build_os=build_os,
                    date=build_date,
                )
            )

    return builds


def find_local_builds(download_dir, os_filter=None, filter_build_type=None):
    """Find already downloaded/extracted Blender builds in the download directory.

    Only archives matching `os_filter`'s suffixes are considered; it defaults to
    the OS we are running on."""
    if os_filter is None:
        os_filter = detect_os()
    download_path = pathlib.Path(download_dir).expanduser().absolute()
    builds = {}
    suffixes = archive_suffixes_for_filter(os_filter)

    archives = [
        archive
        for suffix in suffixes
        for archive in download_path.glob(f"blender-*{suffix}")
    ]
    for archive in archives:
        filename = archive.name
        extract_dir = archive_extract_path(archive)

        # Try to read date from .date file, otherwise use mtime
        date_file = archive.with_suffix(archive.suffix + ".date")
        date = None
        if date_file.exists():
            try:
                date = datetime.datetime.fromisoformat(date_file.read_text().strip())
            except Exception:
                pass

        if not date:
            try:
                date = datetime.datetime.fromtimestamp(archive.stat().st_mtime)
            except Exception:
                pass

        build_type=infer_build_type_from_filename(filename)
        if filter_build_type != None:
            if isinstance(filter_build_type, String):
                if build_type != filter_build_type:
                    continue
            elif isinstance(filter_build_type, Iterable) and all(isinstance(s, String) for s in filter_build_type):
                if not any(build_type == s for s in filter_build_type):
                    continue
            else:
                raise TypeError("filter_build_type must be either None, a string or an iterable of strings!")

        builds[filename] = BlenderBuild(
            filename=filename,
            archive_path=archive,
            build_type=infer_build_type_from_filename(filename),
            build_os=infer_build_os_from_filename(filename),
            downloaded=True,
            extracted=extract_dir.exists(),
            extract_path=extract_dir if extract_dir.exists() else None,
            date=date,
        )

    return builds


def merge_builds(remote_builds, local_builds):
    """Merge remote and local build lists, preferring local info when available. Returns iterable of deduped builds sorted by date."""
    merged = {}

    # start with remote builds
    for build in remote_builds:
        merged[build.filename] = build

    # overlay local info
    for filename, local in local_builds.items():
        if filename in merged:
            remote = merged[filename]
            local.download_url = remote.download_url
            local.build_type = remote.build_type
            local.build_os = remote.build_os or local.build_os
            # prefer scraper date if we have it and it seems newer or we don't have local date
            if remote.date and (not local.date or remote.date > local.date):
                local.date = remote.date
        merged[filename] = local

    # sort using the sort_key which prioritizes date descending
    return sorted(merged.values(), key=lambda b: b.sort_key, reverse=True)


async def download_build(url, save_path, progress_cb=None, chunk_size=1024 * 1024, fallback_date=None):
    """Download a build archive with progress reporting."""
    save_path = pathlib.Path(save_path)
    tmp_path = save_path.with_suffix(save_path.suffix + ".part")

    def cleanup_tmp():
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    try:
        async with aiohttp.ClientSession() as session, session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Download failed: HTTP {response.status}")

            total = response.content_length or 0
            downloaded = 0
            last_modified = response.headers.get("Last-Modified")

            async with aiofiles.open(tmp_path, "wb") as f:
                async for chunk in response.content.iter_chunked(chunk_size):
                    downloaded += await f.write(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total, "Downloading...")

        tmp_path.rename(save_path)
    except asyncio.CancelledError:
        cleanup_tmp()
        raise
    except Exception:
        cleanup_tmp()
        raise

    # determine date: header first, then fallback
    date = fallback_date
    if last_modified:
        try:
            from email.utils import parsedate_to_datetime
            date = parsedate_to_datetime(last_modified)
        except :
            date = fallback_date

    if date:
        try:
            import os
            mtime = date.timestamp()
            os.utime(save_path, (mtime, mtime))
            # save .date file
            date_file = save_path.with_suffix(save_path.suffix + ".date")
            date_file.write_text(date.isoformat())
        except Exception:
            pass

    return save_path


async def extract_build(archive_path, progress_cb=None):
    """Extract a .tar.xz archive with progress reporting."""
    archive_path = pathlib.Path(archive_path)
    if not archive_path.name.endswith(EXTRACTABLE_SUFFIXES):
        raise Exception(
            f"Don't know how to extract {archive_path.name}; "
            f"only {', '.join(EXTRACTABLE_SUFFIXES)} archives are supported"
        )
    extract_dir = archive_extract_path(archive_path)

    def cleanup_extract_dir():
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)

    try:
        if progress_cb:
            progress_cb(0, 0, "Listing archive contents...")

        # count files for progress tracking
        list_proc = await asyncio.create_subprocess_exec(
            "tar", "-tJf", str(archive_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await list_proc.communicate()
        if list_proc.returncode != 0:
            detail = stderr.decode(errors="replace").strip()
            if detail:
                raise Exception(f"Failed to inspect archive: {detail}")
            raise Exception(f"Failed to inspect archive: tar exited with code {list_proc.returncode}")
        total_files = sum(1 for line in stdout.decode(errors="replace").splitlines() if line.strip())

        if progress_cb:
            progress_cb(0, total_files, "Extracting...")

        # extract with verbose to track progress
        proc = await asyncio.create_subprocess_exec(
            "tar", "-C", str(extract_dir.parent), "-xJvf", str(archive_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        extracted = 0
        async for line in proc.stdout:
            extracted += 1
            if progress_cb and extracted % 50 == 0:  # throttle UI updates
                progress_cb(extracted, total_files, "Extracting...")

        stderr = await proc.stderr.read()
        exitcode = await proc.wait()
        if exitcode != 0:
            detail = stderr.decode(errors="replace").strip()
            if detail:
                raise Exception(f"Extraction failed: tar exited with code {exitcode}: {detail}")
            raise Exception(f"Extraction failed: tar exited with code {exitcode}")

        # sync the date to the extracted directory
        date_file = archive_path.with_suffix(archive_path.suffix + ".date")
        if date_file.exists():
            try:
                shutil.copy2(date_file, extract_dir / ".blenderlauncher-date")
                # also set mtime of the directory
                dt = datetime.datetime.fromisoformat(date_file.read_text().strip())
                mtime = dt.timestamp()
                import os
                os.utime(extract_dir, (mtime, mtime))
            except Exception:
                pass

        if progress_cb:
            progress_cb(total_files, total_files, "Extraction complete")

        return extract_dir
    except asyncio.CancelledError:
        cleanup_extract_dir()
        raise
    except Exception:
        cleanup_extract_dir()
        raise


def blender_executable_path(blender_dir, build_os="linux"):
    """Return the Blender executable inside an extracted build directory."""
    blender_dir = pathlib.Path(blender_dir)

    if build_os in (None, "linux"):
        blender_path = blender_dir / "blender"
    elif build_os == "windows":
        blender_path = blender_dir / "blender.exe"
    elif build_os == "macos":
        if blender_dir.name == "Blender.app":
            blender_path = blender_dir / "Contents" / "MacOS" / "Blender"
        else:
            blender_path = blender_dir / "Blender.app" / "Contents" / "MacOS" / "Blender"
    else:
        raise ValueError(f"Unsupported build OS: {build_os}")

    if not blender_path.exists():
        raise FileNotFoundError(f"Blender executable not found: {blender_path}")
    return blender_path


def launch_blender(blender_dir, build_os="linux"):
    """Launch Blender from the given directory. Returns a subprocess.Popen."""
    import subprocess

    blender_path = blender_executable_path(blender_dir, build_os)
    kwargs = {}
    if build_os == "macos":
        kwargs["cwd"] = str(blender_path.parent)
    return subprocess.Popen([str(blender_path)], **kwargs)


def delete_build(build):
    """Delete a build's archive and/or extracted directory."""
    if build.extract_path and build.extract_path.exists():
        shutil.rmtree(build.extract_path)
    if build.archive_path and build.archive_path.exists():
        build.archive_path.unlink()
        # delete .date file
        date_file = build.archive_path.with_suffix(build.archive_path.suffix + ".date")
        if date_file.exists():
            date_file.unlink()
