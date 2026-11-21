"""Plugin management.

The Lightroom SDK has no API to install, remove or reload plugins, so this works
from outside: plugins placed in Lightroom's Modules folder are auto-loaded at
startup, and removing them there uninstalls them. Changes need a restart.

Lightroom's own preferences are only ever read, never edited.
"""

from __future__ import annotations

import time
import plistlib
import re
import shutil
from pathlib import Path
from typing import Any

from .. import bridge, config, luatable
from . import app

PREFS_PLIST = config.HOME / f"Library/Preferences/{config.LIGHTROOM_BUNDLE_ID}.plist"
_PLUGIN_SUFFIXES = (".lrplugin", ".lrdevplugin")
_MENU_KEYS = {
    "LrExportMenuItems": "File > Plug-in Extras",
    "LrLibraryMenuItems": "Library > Plug-in Extras",
    "LrHelpMenuItems": "Help > Plug-in Extras",
}


def _balanced_block(text: str, start: int) -> str:
    """Text of the {...} block opening at or after `start`."""
    open_at = text.find("{", start)
    if open_at < 0:
        return ""
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_at : i + 1]
    return ""


def _loc(value: str) -> str:
    """'$$$/Some/Key=Shown Text' -> 'Shown Text'."""
    return value.split("=", 1)[1] if value.startswith("$$$/") and "=" in value else value


def read_info(plugin_dir: Path) -> dict[str, Any]:
    """Parse a plugin's Info.lua for its id, name, version and Plug-in Extras menu items."""
    info: dict[str, Any] = {"id": None, "name": plugin_dir.stem, "version": None, "menu_items": []}
    info_file = plugin_dir / "Info.lua"
    try:
        raw = info_file.read_bytes()
    except OSError:
        info["error"] = "Info.lua missing or unreadable"
        return info
    if raw.startswith(b"\x1bLua"):
        info["compiled"] = True  # bytecode: can't read details
        return info
    text = re.sub(r"--\[\[.*?\]\]", "", raw.decode("utf-8", "replace"), flags=re.DOTALL)
    text = re.sub(r"--[^\n]*", "", text)

    def string_field(key: str) -> str | None:
        m = re.search(rf"\b{key}\s*=\s*(?:LOC\s*)?\(?\s*([\"'])(.*?)\1", text)
        return _loc(m.group(2)) if m else None

    info["id"] = string_field("LrToolkitIdentifier")
    info["name"] = string_field("LrPluginName") or info["name"]
    m = re.search(r"\bVERSION\s*=", text)
    if m:
        block = _balanced_block(text, m.end())
        parts = [re.search(rf"\b{k}\s*=\s*(\d+)", block) for k in ("major", "minor", "revision")]
        if parts[0]:
            info["version"] = ".".join(p.group(1) for p in parts if p)
    for key, menu in _MENU_KEYS.items():
        m = re.search(rf"\b{key}\s*=", text)
        if not m:
            continue
        block = _balanced_block(text, m.end())
        for title in re.finditer(r"\btitle\s*=\s*(?:LOC\s*)?\(?\s*([\"'])(.*?)\1", block):
            info["menu_items"].append({"menu": menu, "title": _loc(title.group(2))})
    return info


def _prefs_table(key: str) -> dict[str, Any]:
    try:
        with PREFS_PLIST.open("rb") as fh:
            value = plistlib.load(fh).get(key)
        table = luatable.parse(value) if isinstance(value, str) else {}
        return table if isinstance(table, dict) else {}
    except (OSError, ValueError, plistlib.InvalidFileException):
        return {}


def list_plugins() -> list[dict[str, Any]]:
    """Plugins Lightroom knows about: its Modules folders plus those added in Plug-in Manager."""
    disabled_paths = set(_prefs_table("AgSdkPluginLoader_disabledPluginPaths"))
    disabled_ids = set(_prefs_table("AgSdkPluginLoader_disabledPluginIDs"))
    found: dict[str, dict[str, Any]] = {}

    def add(path: Path, source: str) -> None:
        key = str(path)
        if key in found:
            return
        entry = {"path": key, "source": source, "exists": path.exists(), "is_symlink": path.is_symlink()}
        entry.update(read_info(path) if path.exists() else {"id": None, "name": path.stem, "version": None, "menu_items": []})
        entry["enabled"] = key not in disabled_paths and entry.get("id") not in disabled_ids
        entry["managed"] = source == "user-modules"
        found[key] = entry

    for folder, source in ((config.USER_MODULES_DIR, "user-modules"), (config.SYSTEM_MODULES_DIR, "system-modules")):
        if folder.is_dir():
            for child in sorted(folder.iterdir()):
                if child.suffix in _PLUGIN_SUFFIXES:
                    add(child, source)
    for path in sorted(_prefs_table("AgSdkPluginLoader_installedPluginPaths")):
        add(Path(str(path)), "plugin-manager")
    return list(found.values())


def _find(name: str) -> dict[str, Any]:
    wanted = name.lower()
    matches = [
        p
        for p in list_plugins()
        if wanted in {str(p.get("id") or "").lower(), str(p.get("name") or "").lower(), Path(p["path"]).name.lower(), Path(p["path"]).stem.lower()}
    ]
    if not matches:
        raise LookupError(f"No plugin matching {name!r}. See `lightroom-mcp plugins list`.")
    managed = [p for p in matches if p["managed"]]
    if len(managed) == 1:
        return managed[0]
    if len(matches) > 1:
        raise LookupError(f"{name!r} matches several plugins; use the folder name: " + ", ".join(p["path"] for p in matches))
    return matches[0]


def install(source: str, link: bool = False, force: bool = False, restart: bool = False) -> dict[str, Any]:
    """Install a .lrplugin folder into Lightroom's Modules folder (copy, or symlink with link=True)."""
    src = Path(source).expanduser().resolve()
    if src.suffix not in _PLUGIN_SUFFIXES or not src.is_dir():
        raise ValueError(f"{src} is not a .lrplugin folder")
    if not (src / "Info.lua").exists():
        raise ValueError(f"{src} has no Info.lua, so Lightroom would not load it")
    dest = config.USER_MODULES_DIR / src.name
    if dest.exists() or dest.is_symlink():
        if not force:
            raise FileExistsError(f"{dest} already exists. Use force to replace it.")
        _remove(dest)
    config.USER_MODULES_DIR.mkdir(parents=True, exist_ok=True)
    if link:
        dest.symlink_to(src, target_is_directory=True)
    else:
        shutil.copytree(src, dest)
    out: dict[str, Any] = {"installed": str(dest), "linked": link, "info": read_info(dest)}
    if restart:
        out["restart"] = app.restart()
    else:
        out["note"] = "Restart Lightroom for the plugin to load."
    return out


def _remove(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    else:
        shutil.rmtree(path)


def uninstall(name: str, restart: bool = False) -> dict[str, Any]:
    """Remove a plugin from the user Modules folder. Other plugins must be removed in Plug-in Manager."""
    plugin = _find(name)
    if not plugin["managed"]:
        raise PermissionError(
            f"{plugin['path']} was not installed in {config.USER_MODULES_DIR}. "
            "Remove it in Lightroom's Plug-in Manager (File > Plug-in Manager)."
        )
    path = Path(plugin["path"])
    _remove(path)
    out: dict[str, Any] = {"removed": str(path)}
    if restart:
        out["restart"] = app.restart()
    else:
        out["note"] = "Restart Lightroom to finish unloading the plugin."
    return out


def install_bridge(link: bool = False, restart: bool = False) -> dict[str, Any]:
    """Install (or update) the LightroomBridge plugin this tool talks to."""
    return install(str(config.BRIDGE_PLUGIN_SOURCE), link=link, force=True, restart=restart)


def reload_bridge(wait: float = 20.0) -> dict[str, Any]:
    """Reload the whole bridge plugin in place: its server, dispatcher and command handlers."""
    try:
        before = bridge.call("bridge.restart").get("generation")
    except bridge.BridgeError as exc:
        if "unknown command" not in str(exc):
            raise
        # A bridge from before full reload existed: it can only re-read its handlers.
        return {**bridge.call("bridge.reload"), "scope": "handlers"}
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        time.sleep(0.5)
        try:
            generation = bridge.call("status", timeout=3).get("generation")
        except bridge.BridgeError:
            continue
        if generation is not None and generation != before:
            return {"reloaded": True, "scope": "plugin", "generation": generation}
    raise RuntimeError(
        f"The bridge did not come back within {wait:g}s of the reload. "
        "Check that Lightroom is responsive; restarting Lightroom reloads the plugin too."
    )


def reload(name: str | None = None, restart: bool = False) -> dict[str, Any]:
    """Reload a plugin. The bridge reloads its own command handlers live; any other plugin needs a restart."""
    if name is None or name.lower() in (config.BRIDGE_PLUGIN_ID, "lightroombridge", "bridge", config.BRIDGE_PLUGIN_DIRNAME.lower()):
        return reload_bridge()
    plugin = _find(name)
    if not restart:
        raise RuntimeError(
            f"Lightroom has no API to reload {plugin['name']!r} in place. "
            "Pass restart to quit and relaunch Lightroom, or use Reload Plug-in in Plug-in Manager."
        )
    return {"plugin": plugin["name"], "restart": app.restart()}


def list_extras() -> list[dict[str, Any]]:
    """Plug-in Extras menu items declared by each plugin, and whether this tool can run them."""
    items = []
    for plugin in list_plugins():
        for item in plugin.get("menu_items", []):
            items.append(
                {
                    "plugin": plugin["name"],
                    "plugin_id": plugin.get("id"),
                    "menu": item["menu"],
                    "title": item["title"],
                    "runnable": plugin.get("id") == config.BRIDGE_PLUGIN_ID,
                }
            )
    return items


def run_extra(plugin: str, title: str) -> dict[str, Any]:
    """Run a Plug-in Extras command. Only the bridge plugin's own commands can be run."""
    found = _find(plugin)
    if found.get("id") != config.BRIDGE_PLUGIN_ID:
        raise PermissionError(
            f"Can't run {title!r} from {found['name']!r}: the Lightroom SDK does not let one plugin "
            "invoke another plugin's menu commands. Run it from the Plug-in Extras menu in Lightroom."
        )
    return bridge.call("bridge.runExtra", {"title": title})
