"""Paths and settings shared by the CLI, the MCP server and the bridge client."""

from __future__ import annotations

import json
import os
from pathlib import Path

HOME = Path.home()

LIGHTROOM_BUNDLE_ID = "com.adobe.LightroomClassicCC7"
LIGHTROOM_SUPPORT_DIR = HOME / "Library/Application Support/Adobe/Lightroom"
USER_MODULES_DIR = LIGHTROOM_SUPPORT_DIR / "Modules"
SYSTEM_MODULES_DIR = Path("/Library/Application Support/Adobe/Lightroom/Modules")

STATE_DIR = HOME / "Library/Application Support/lightroom-mcp"
BRIDGE_STATE_FILE = STATE_DIR / "bridge.json"

BRIDGE_PLUGIN_ID = "com.lightroommcp.bridge"
BRIDGE_PLUGIN_DIRNAME = "LightroomBridge.lrplugin"
BRIDGE_PLUGIN_SOURCE = Path(__file__).parent / "lrplugin" / BRIDGE_PLUGIN_DIRNAME

DEFAULT_COMMAND_PORT = 58763  # plugin receives commands here
RESPONSE_DIR = STATE_DIR / "responses"  # plugin writes one reply file per request here

DEFAULT_CATALOG = HOME / "Pictures/Lightroom/Lightroom Catalog.lrcat"


def catalog_path() -> Path:
    """Catalog to read: $LIGHTROOM_CATALOG, else the default, else the only .lrcat in ~/Pictures/Lightroom."""
    env = os.environ.get("LIGHTROOM_CATALOG")
    if env:
        return Path(env).expanduser()
    if DEFAULT_CATALOG.exists():
        return DEFAULT_CATALOG
    candidates = sorted((HOME / "Pictures/Lightroom").glob("*.lrcat"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(
        "No Lightroom catalog found. Set LIGHTROOM_CATALOG to the path of your .lrcat file."
    )


def bridge_port() -> int:
    """Command port: env override, else what the plugin last wrote, else the default."""
    env = os.environ.get("LIGHTROOM_BRIDGE_PORT")
    if env:
        return int(env)
    try:
        return int(json.loads(BRIDGE_STATE_FILE.read_text())["commandPort"])
    except (OSError, ValueError, KeyError, TypeError):
        return DEFAULT_COMMAND_PORT
