from __future__ import annotations

import json
import plistlib
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from lightroom_mcp import config
from lightroom_mcp.core import plugins

INFO = """
-- a comment with title = "not this"
return {
    LrSdkVersion = 6.0,
    LrToolkitIdentifier = 'com.example.sample',
    LrPluginName = LOC "$$$/Sample/Name=Sample Plugin",
    LrExportMenuItems = {
        { title = "Do Thing...", file = "DoThing.lua" },
        { title = LOC "$$$/Sample/Other=Other Thing", file = "Other.lua", enabledWhen = "photosSelected" },
    },
    LrLibraryMenuItems = { { title = "Library Thing", file = "Lib.lua" } },
    VERSION = { major = 1, minor = 2, revision = 3, build = 4 },
}
"""


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    modules = tmp_path / "Modules"
    monkeypatch.setattr(config, "USER_MODULES_DIR", modules)
    monkeypatch.setattr(config, "SYSTEM_MODULES_DIR", tmp_path / "SystemModules")
    prefs = tmp_path / "prefs.plist"
    monkeypatch.setattr(plugins, "PREFS_PLIST", prefs)
    sample = tmp_path / "src" / "Sample.lrplugin"
    sample.mkdir(parents=True)
    (sample / "Info.lua").write_text(INFO)
    return {"modules": modules, "prefs": prefs, "sample": sample, "tmp": tmp_path}


def test_read_info(env):
    info = plugins.read_info(env["sample"])
    assert info["id"] == "com.example.sample"
    assert info["name"] == "Sample Plugin"
    assert info["version"] == "1.2.3"
    assert info["menu_items"] == [
        {"menu": "File > Plug-in Extras", "title": "Do Thing..."},
        {"menu": "File > Plug-in Extras", "title": "Other Thing"},
        {"menu": "Library > Plug-in Extras", "title": "Library Thing"},
    ]


def test_read_info_of_bundled_bridge_plugin():
    info = plugins.read_info(config.BRIDGE_PLUGIN_SOURCE)
    assert info["id"] == config.BRIDGE_PLUGIN_ID
    assert {"menu": "Library > Plug-in Extras", "title": "Bridge Status"} in info["menu_items"]


def test_bridge_plugin_version_matches_package():
    pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    info = plugins.read_info(config.BRIDGE_PLUGIN_SOURCE)
    assert info["version"] == pyproject["project"]["version"], (
        "Run scripts/sync_plugin_version.py to update Info.lua"
    )


def test_install_list_uninstall(env):
    out = plugins.install(str(env["sample"]))
    dest = env["modules"] / "Sample.lrplugin"
    assert out["installed"] == str(dest) and (dest / "Info.lua").exists()
    assert "Restart" in out["note"]

    with pytest.raises(FileExistsError):
        plugins.install(str(env["sample"]))
    plugins.install(str(env["sample"]), force=True, link=True)
    assert dest.is_symlink()

    listed = plugins.list_plugins()
    assert [(p["name"], p["source"], p["managed"], p["enabled"]) for p in listed] == [
        ("Sample Plugin", "user-modules", True, True)
    ]

    plugins.uninstall("com.example.sample")
    assert not dest.exists() and not dest.is_symlink()
    assert env["sample"].exists(), "uninstalling a symlinked plugin must not delete its source"


def test_install_rejects_non_plugins(env):
    with pytest.raises(ValueError):
        plugins.install(str(env["tmp"]))
    empty = env["tmp"] / "Empty.lrplugin"
    empty.mkdir()
    with pytest.raises(ValueError):
        plugins.install(str(empty))


def test_plugin_manager_plugins_are_listed_but_not_removable(env):
    path = str(env["sample"])
    with env["prefs"].open("wb") as fh:
        plistlib.dump(
            {
                "AgSdkPluginLoader_installedPluginPaths": f't = {{\n\t["{path}"] = "{path}",\n\t["/gone/Old.lrplugin"] = "/gone/Old.lrplugin",\n}}\n',
                "AgSdkPluginLoader_disabledPluginPaths": f't = {{\n\t["{path}"] = true,\n}}\n',
            },
            fh,
        )
    listed = {p["path"]: p for p in plugins.list_plugins()}
    assert listed[path]["source"] == "plugin-manager"
    assert listed[path]["enabled"] is False
    assert listed["/gone/Old.lrplugin"]["exists"] is False
    with pytest.raises(PermissionError, match="Plug-in Manager"):
        plugins.uninstall("Sample Plugin")
    assert env["sample"].exists()


def test_extras_only_runnable_for_bridge(env):
    plugins.install(str(env["sample"]))
    extras = plugins.list_extras()
    assert len(extras) == 3 and not any(e["runnable"] for e in extras)
    with pytest.raises(PermissionError, match="does not let one plugin"):
        plugins.run_extra("Sample Plugin", "Do Thing...")
    with pytest.raises(RuntimeError, match="no API to reload"):
        plugins.reload("Sample Plugin")


@pytest.mark.skipif(shutil.which("luajit") is None, reason="luajit not installed")
def test_lua_json_roundtrip(tmp_path):
    """The plugin's JSON module must agree with Python's json in both directions."""
    payload = {"id": 7, "command": "x", "params": {"ids": [1, 2, 3], "s": 'q"uo\\te\n', "u": "café \U0001f600", "f": 0.25, "t": True, "n": None, "e": [], "neg": -3}}
    script = tmp_path / "roundtrip.lua"
    script.write_text(
        f'package.path = "{config.BRIDGE_PLUGIN_SOURCE}/?.lua;" .. package.path\n'
        'local JSON = require "JSON"\n'
        "local value = JSON.decode(io.read('*a'))\n"
        "assert(value.params.ids[3] == 3 and value.params.t == true and value.params.n == nil)\n"
        "io.write(JSON.encode(value))\n"
    )
    result = subprocess.run(["luajit", str(script)], input=json.dumps(payload), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    expected = json.loads(json.dumps(payload))
    del expected["params"]["n"]  # Lua tables can't hold nil
    assert json.loads(result.stdout) == expected


@pytest.mark.skipif(shutil.which("luajit") is None, reason="luajit not installed")
def test_bridge_plugin_lifecycle_in_lua(tmp_path):
    """Load, command dispatch, duplicate protection, handler reload and full restart, against SDK stand-ins."""
    harness = Path(__file__).parent / "lua" / "harness.lua"
    result = subprocess.run(
        ["luajit", str(harness), str(config.BRIDGE_PLUGIN_SOURCE), str(tmp_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "OK"
