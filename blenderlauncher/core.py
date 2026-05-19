import asyncio
import datetime
import pathlib
import re
import shutil
from dataclasses import dataclass, field
from typing import Callable, Optional

import aiofiles
import aiohttp
import yarl
from bs4 import BeautifulSoup


@dataclass
class BlenderBuild:
    """Represents a Blender daily build, either remote or local or both."""

    filename: str
    download_url: Optional[str] = None
    archive_path: Optional[pathlib.Path] = None
    extract_path: Optional[pathlib.Path] = None
    build_type: str = "unknown"
    downloaded: bool = False
    extracted: bool = False
    date: Optional[datetime.datetime] = None

    @property
    def display_name(self):
        name = self.filename
        # strip platform and extension to get a clean version string
        name = re.sub(r"-linux-x86_64", "", name)
        name = re.sub(r"-linux64", "", name)
        name = re.sub(r"\.tar\.xz$", "", name)
        return name

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


async def scrape_daily_builds():
    """Scrape the Blender daily builds page and return available builds."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://builder.blender.org/download/daily/"
        ) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to fetch daily builds page: HTTP {resp.status}")
            html_text = await resp.text()

    html = BeautifulSoup(html_text, features="lxml")
    builds = []

    rows = html.select("li.t-row.build")
    for row in rows:
        # Extract date once per row
        date_cell = row.find("div", class_="b-date")
        build_date = None
        if date_cell and "title" in date_cell.attrs:
            try:
                build_date = datetime.datetime.fromisoformat(date_cell.attrs["title"])
            except Exception:
                pass

        for a in row.find_all("a"):
            cls = a.get("class", [])
            if "plausible-event-os=linux" not in cls:
                continue
            if "plausible-event-name=Downloads+Blender" not in cls:
                continue
            url_str = a.attrs.get("href", "")
            if not url_str.endswith(".xz"):
                continue

            # Discover the branch dynamically from the plausible-event-build=<X> class
            build_type = None
            for c in cls:
                if c.startswith("plausible-event-build="):
                    build_type = c.split("=", 1)[1]
                    break
            if not build_type:
                continue

            url = yarl.URL(url_str)
            filename = url.parts[-1]
            builds.append(
                BlenderBuild(
                    filename=filename,
                    download_url=str(url),
                    build_type=build_type,
                    date=build_date,
                )
            )

    return builds


def find_local_builds(download_dir):
    """Find already downloaded/extracted Blender builds in the download directory."""
    download_path = pathlib.Path(download_dir).expanduser().absolute()
    builds = {}

    for archive in download_path.glob("blender-*.tar.xz"):
        filename = archive.name
        extract_dir = archive.with_suffix("").with_suffix("")  # strip .tar.xz
        
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

        builds[filename] = BlenderBuild(
            filename=filename,
            archive_path=archive,
            build_type=infer_build_type_from_filename(filename),
            downloaded=True,
            extracted=extract_dir.exists(),
            extract_path=extract_dir if extract_dir.exists() else None,
            date=date,
        )

    return builds


def merge_builds(remote_builds, local_builds):
    """Merge remote and local build lists, preferring local info when available."""
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

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
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
    
    # determine date: header first, then fallback
    date = fallback_date
    if last_modified:
        try:
            from email.utils import parsedate_to_datetime
            date = parsedate_to_datetime(last_modified)
        except Exception:
            pass

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
    extract_dir = archive_path.with_suffix("").with_suffix("")

    if progress_cb:
        progress_cb(0, 0, "Listing archive contents...")

    # count files for progress tracking
    list_proc = await asyncio.create_subprocess_exec(
        "tar", "-tJf", str(archive_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await list_proc.communicate()
    total_files = len(stdout.decode().strip().split("\n")) if stdout else 0

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

    exitcode = await proc.wait()
    if exitcode != 0:
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


def launch_blender(blender_dir):
    """Launch Blender from the given directory. Returns a subprocess.Popen."""
    import subprocess

    blender_path = pathlib.Path(blender_dir) / "blender"
    if not blender_path.exists():
        raise FileNotFoundError(f"Blender executable not found: {blender_path}")
    return subprocess.Popen([str(blender_path)])


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
