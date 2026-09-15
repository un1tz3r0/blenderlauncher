"""Checks that metadata which cannot be derived from a single source agrees.

The desktop entry, AppStream metainfo and Flatpak manifest are static files read
by tools that cannot import Python, so they repeat values that `blenderlauncher`
and `pyproject.toml` also define. These tests fail when one copy changes without
the others.
"""

import configparser
import pathlib
import re
import struct
import tomllib
import xml.etree.ElementTree as ET

import pytest
import yaml

import blenderlauncher
from blenderlauncher import APP_ID, APP_NAME, APP_SUMMARY, settings

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE_DIR = pathlib.Path(blenderlauncher.__file__).parent


@pytest.fixture(scope="module")
def pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


@pytest.fixture(scope="module")
def manifest():
    manifests = [p for p in ROOT.glob("*.yml") if "app-id" in yaml.safe_load(p.read_text())]
    assert len(manifests) == 1, f"expected one Flatpak manifest, found {manifests}"
    return yaml.safe_load(manifests[0].read_text())


@pytest.fixture(scope="module")
def desktop():
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # keys are case-sensitive
    parser.read(ROOT / "data" / f"{APP_ID}.desktop")
    return parser["Desktop Entry"]


@pytest.fixture(scope="module")
def metainfo():
    return ET.parse(ROOT / "data" / f"{APP_ID}.metainfo.xml").getroot()


def test_version_matches_pyproject(pyproject):
    assert blenderlauncher.__version__ == pyproject["project"]["version"]


def test_app_id(manifest, desktop, metainfo):
    assert manifest["app-id"] == APP_ID
    assert desktop["Icon"] == APP_ID
    assert desktop["StartupWMClass"] == APP_ID
    assert metainfo.findtext("id") == APP_ID
    assert metainfo.findtext("launchable[@type='desktop-id']") == f"{APP_ID}.desktop"


def test_app_name_and_summary(desktop, metainfo):
    assert desktop["Name"] == APP_NAME
    assert metainfo.findtext("name") == APP_NAME
    assert desktop["Comment"] == APP_SUMMARY
    assert metainfo.findtext("summary") == APP_SUMMARY


def test_gui_command(pyproject, manifest, desktop):
    gui_scripts = pyproject["project"]["gui-scripts"]
    assert manifest["command"] in gui_scripts
    assert desktop["Exec"].split()[0] == manifest["command"]


def test_license(pyproject, metainfo):
    license_text = (ROOT / "LICENSE").read_text()
    assert metainfo.findtext("project_license") == "MIT"
    assert "MIT License" in license_text


def test_flatpak_config_permission_matches_settings(manifest):
    # settings.config_dir() and settings.default_download_dir() rely on these
    # permissions inside the Flatpak.
    assert f"--filesystem=xdg-config/{settings.CONFIG_DIR.name}:create" in manifest["finish-args"]
    assert "--filesystem=xdg-config/user-dirs.dirs:ro" in manifest["finish-args"]


def test_flatpak_installs_locked_dependencies(manifest):
    modules = {m["name"]: m for m in manifest["modules"]}
    sources = [s.get("path") for s in modules["python-deps"]["sources"]]
    assert "flatpak-requirements.txt" in sources
    assert "--no-deps" in " ".join(modules["blenderlauncher"]["build-commands"])


def test_defaults_are_not_repeated_at_call_sites():
    # settings.load() fills in every DEFAULTS key, so `.get("key", fallback)`
    # on a loaded config would be a second, drift-prone copy of the default
    keys = "|".join(map(re.escape, settings.DEFAULTS))
    pattern = re.compile(rf"""\.get\(\s*["']({keys})["']""")
    offenders = [
        f"{path.name}:{lineno}"
        for path in PACKAGE_DIR.glob("*.py")
        if path.name != "settings.py"
        for lineno, line in enumerate(path.read_text().splitlines(), 1)
        if pattern.search(line)
    ]
    assert not offenders


@pytest.mark.parametrize("png", sorted((ROOT / "icons").glob("blenderlauncher_*px.png")), ids=lambda p: p.name)
def test_icon_png_size_matches_name(png):
    # install-data.sh installs each PNG into hicolor/NxN based on its filename
    size = int(png.name.rsplit("_", 1)[1].removesuffix("px.png"))
    width, height = struct.unpack(">II", png.read_bytes()[16:24])
    assert (width, height) == (size, size)


def test_config_dir_follows_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings.config_dir() == tmp_path / "blenderlauncher"


def test_config_dir_shared_with_host_in_flatpak(monkeypatch, tmp_path):
    monkeypatch.setenv("FLATPAK_ID", APP_ID)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings.config_dir() == pathlib.Path.home() / ".config" / "blenderlauncher"


def test_default_download_dir_shared_with_host_in_flatpak(monkeypatch, tmp_path):
    home = tmp_path / "home"
    config_home = home / ".config"
    config_home.mkdir(parents=True)
    (config_home / "user-dirs.dirs").write_text('XDG_DOWNLOAD_DIR="$HOME/Téléchargements"\n')
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("FLATPAK_ID", APP_ID)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "flatpak-config"))
    assert settings.default_download_dir() == "~/Téléchargements"
