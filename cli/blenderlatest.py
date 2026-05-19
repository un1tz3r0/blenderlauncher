import asyncio
import datetime
import os
import pathlib
import sys

import aiofiles
import aiohttp
import yarl
from bs4 import BeautifulSoup


async def ext_wget(url, save_path=None):
    p = await asyncio.subprocess.create_subprocess_exec(
        "wget", "-O", str(save_path), "-c", str(url)
    )
    return await p.wait()


async def wget(url, save_path=None, chunk_size=1024 * 1024, **kwargs):
    url = yarl.URL(url).update_query(kwargs)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"HTTP status: {response.status}")
            if save_path == None:
                buffer = bytearray()
                async for chunk in response.content.iter_chunked(chunk_size):
                    buffer.extend(chunk)
                return response.content_type, buffer
            else:
                async with aiofiles.open(save_path, "wb") as f:
                    bytes_written = 0
                    async for chunk in response.content.iter_chunked(chunk_size):
                        bytes_written = bytes_written + await f.write(chunk)
                        print(f"Wrote {bytes_written} bytes...\r", end="")
                    return response.content_type, bytes_written


async def daily_blender_builds_page(
    downloaddir="~/Downloads",
    nodownload=False,
    forcedownload=False,
    cleanup=False,
    skip=None,
    show=None,
):
    # fetch and parse the daily builds page
    mimetype, data = await wget("https://builder.blender.org/download/daily/")
    html = BeautifulSoup(data.decode("utf-8"), features="lxml")
    
    # get a list of downloaded files sorted by date
    downloadpaths = list(
        sorted(
            pathlib.Path(downloaddir).expanduser().absolute().glob("blender-*.xz"),
            key=lambda p: p.stat().st_mtime,
        )
    )
    if show:
        print("Previously downloaded versions:")
        for i, downloadpath in enumerate(reversed(downloadpaths)):
            mtime = datetime.datetime.fromtimestamp(downloadpath.stat().st_mtime)
            print(f"{i}: {downloadpath.name} (downloaded on {mtime})")
        return None

    # if we should download the latest version
    if not nodownload and (skip == None or skip == 0):
        # find the latest build link
        downloadurl = None
        for buildtype in ["alpha", "beta", "stable"]:
            rows = html.select("li.t-row.build")
            for row in rows:
                # Look for the download link for linux and this build type
                for a in row.find_all("a"):
                    cls = a.get("class", [])
                    if (f"plausible-event-os=linux" in cls and \
                        f"plausible-event-build={buildtype}" in cls and \
                        "plausible-event-name=Downloads+Blender" in cls):
                        url = yarl.URL(a.attrs.get("href", ""))
                        if url.parts[-1].endswith(".xz"):
                            downloadurl = url
                            break
                if downloadurl:
                    break
            if downloadurl:
                break
        # if we didn't find a download link, print an error and return None
        if downloadurl == None:
            print("Error: No download link found!")
            return None
        # check if the downloaded file exists yet
        downloadpath = (
            pathlib.Path(downloaddir).expanduser().absolute() / downloadurl.parts[-1]
        )
        # if not downloadpath.exists():
        print(f"Downloading {downloadurl} to {downloadpath}")
        exitcode = await ext_wget(downloadurl, str(downloadpath))
        if exitcode != 0:
            print(f"Download failed, wget exited with code {exitcode}...")
            if forcedownload:
                return None
        # print(f"Downloaded {size} bytes of type {mimetype} to {downloadpath}")
        if not forcedownload:
            downloadpaths = downloadpaths + [downloadpath]
        else:
            downloadpaths = [downloadpath]
    print(f"Downloaded version: {downloadpaths}")
    # expand if needed and clean up old versions... result will hold the latest expanded version
    result = None
    for downloadpath in reversed(downloadpaths):
        # Skip the latest n versions
        if skip != None and skip > 0:
            skip = skip - 1
            continue
        # check if the downloaded file has been expanded yet
        expandedpath = downloadpath.with_suffix("").with_suffix("")
        if result == None:
            # expand the latest archive if needed
            if not expandedpath.exists():
                print(f"Expanding {downloadpath} to {expandedpath}")
                exitstatus = await (
                    await asyncio.create_subprocess_exec(
                        "tar",
                        "-C",
                        str(expandedpath.parent),
                        "-xJvf",
                        str(downloadpath.absolute()),
                    )
                ).wait()
                if exitstatus != 0:
                    print(
                        f"Error expanding {downloadpath}! tar exited with code {exitstatus}"
                    )
                else:
                    print(f"Expanded {downloadpath} to {expandedpath}")
                    result = expandedpath
            else:
                print(f"Expanded {downloadpath} already exists in {expandedpath}")
                result = expandedpath
        if result != None and cleanup:
            cleanupfiles = [str(downloadpath)]
            if expandedpath.exists():
                cleanupfiles = cleanupfiles + [str(expandedpath)]
            print(f"Cleaning up old version: {cleanupfiles}")
            exitstatus = await (
                await asyncio.create_subprocess_exec(
                    "rm", "-rf", str(expandedpath), str(downoadpath)
                )
            ).wait()
            if exitstatus != 0:
                print("rm exited with non-zero status {exitstatus}")
    return result


async def async_main(
    download_dir="~/Downloads",
    no_download=False,
    no_run=False,
    verbose=False,
    force=False,
    cleanup=False,
    last=None,
    show=None,
):
    # allow skipping download and most recent previous versions using -l/--last
    skip = 0
    if last != None and last > 0:
        skip = last

    # loop while trying out versions, until we find one that runs successfully
    while True:
        try:
            print(f"--- Trying #{skip + 1} most recent version... ---")
            result = await daily_blender_builds_page(
                downloaddir=download_dir,
                nodownload=no_download,
                forcedownload=force,
                cleanup=cleanup,
                skip=skip,
                show=show,
            )
            if result == None:
                print("No more downloaded versions to try... exiting!")
                break
            resultpath = pathlib.Path(result)
            if no_run:
                print(f"{str(resultpath / 'blender')}")
                break
            else:
                print(f"Running: {str(resultpath / 'blender')}")
                import asyncio.subprocess

                p = await asyncio.create_subprocess_exec(str(resultpath / "blender"))
                if await p.wait() != 0:
                    raise RuntimeError("Subprocess exited abnormally...")
                else:
                    print("Successfully ran blender, exit status is 0. Exiting.")
                    break
        except Exception as err:
            print(f"Error: {err}, retrying...")
        skip = skip + 1
    print("byeee!")


if __name__ == "__main__":
    import argparse

    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(
        description="Download and/or launch the latest experimental build of blender from blender.org."
    )

    # Add arguments
    parser.add_argument(
        "-d",
        "--download-dir",
        help="The download directory path, default is $HOME/Downloads",
        required=False,
        default="~/Downloads",
    )
    parser.add_argument(
        "-D",
        "--no-download",
        help="Do not download anything, just expand and run the latest blender version in the downloads folder",
        action="store_true",
    )
    parser.add_argument(
        "-f",
        "--force",
        help="Only use the latest version, fail if download fails, do not fall back to previous downloaded versions",
        action="store_true",
    )
    parser.add_argument(
        "-c",
        "--cleanup",
        help="Clean up older versions when a newer one is downloaded successfully.",
        action="store_true",
    )
    parser.add_argument(
        "-r",
        "--no-run",
        help="Do not run blender, just print out the path to the executable that would otherwise be started",
        action="store_true",
    )
    parser.add_argument(
        "-v", "--verbose", help="Enable verbose output", action="store_true"
    )
    parser.add_argument(
        "-l",
        "--last",
        help="Use the nth most recently already downloaded version (implies --no-download/-D), useful when the newest build is broken.",
        type=int,
        required=False,
        default=0,
    )
    parser.add_argument(
        "-s",
        "--show",
        help="Show a numbered list of previously downloaded versions, in the same order as used with --last/-l.",
        action="store_true",
        required=False,
    )
    # Parse the arguments
    args = parser.parse_args()

    asyncio.run(async_main(**args.__dict__))
