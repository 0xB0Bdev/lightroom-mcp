"""FastMCP server exposing the same operations as the CLI, over stdio."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from .core import app as app_ops
from .core import develop as develop_ops
from .core import export as export_ops
from .core import organize as organize_ops
from .core import plugins as plugin_ops
from .core import search as search_ops

INSTRUCTIONS = """\
Control Adobe Lightroom Classic.

Photos are identified by integer catalog ids; get them from search_photos or selected_photos.
Tools that act on photos take either `ids` or `selected=true` (the current Lightroom selection).

search_photos, get_photo, list_collections, list_keywords and list_plugins read files directly
and work with Lightroom closed. Everything else needs Lightroom running with the bridge plugin
installed; if a tool reports the bridge is unreachable, call install_bridge_plugin (and restart).

Develop setting names are Lightroom's own (Exposure2012, Contrast2012, Highlights2012,
Shadows2012, Temperature, Tint, Vibrance, Saturation, ...). Call get_develop_settings on a photo
to see the available names and current values before changing them.
"""

mcp = FastMCP("lightroom", instructions=INSTRUCTIONS)

READ = {"readOnlyHint": True}
WRITE = {"readOnlyHint": False, "destructiveHint": False}
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True}


# --- read ----------------------------------------------------------------------


@mcp.tool(annotations=READ)
def status() -> dict[str, Any]:
    """Catalog path and counts, plus live Lightroom state (version, module, selection) if the bridge is reachable."""
    return search_ops.status()


@mcp.tool(annotations=READ)
def search_photos(
    text: str | None = None,
    rating: str | None = None,
    flag: str | None = None,
    label: str | None = None,
    camera: str | None = None,
    lens: str | None = None,
    after: str | None = None,
    before: str | None = None,
    keyword: str | None = None,
    collection: str | None = None,
    folder: str | None = None,
    format: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Find photos in the catalog. All filters are optional and combine with AND.

    text/camera/lens/folder: case-insensitive substring of file name, camera model, lens, folder path.
    rating: '4', '>=3', '<2'. flag: picked | rejected | unflagged. label: red | yellow | green | blue | purple | none.
    after/before: capture date as YYYY-MM-DD. keyword: exact keyword. collection: name or id. format: RAW, JPG, DNG...
    Returns {total, offset, photos}; page with limit/offset.
    """
    return search_ops.search_photos(
        text=text, rating=rating, flag=flag, label=label, camera=camera, lens=lens, after=after,
        before=before, keyword=keyword, collection=collection, folder=folder, format=format,
        limit=min(limit, 500), offset=offset,
    )


@mcp.tool(annotations=READ)
def get_photo(photo_id: int, include_develop: bool = False) -> dict[str, Any]:
    """One photo's file path, EXIF, rating, keywords, collections and caption; optionally its saved develop settings."""
    return search_ops.get_photo(photo_id, include_develop=include_develop)


@mcp.tool(annotations=READ)
def list_collections() -> list[dict[str, Any]]:
    """Collections, smart collections and collection sets."""
    return search_ops.list_collections()


@mcp.tool(annotations=READ)
def list_keywords() -> list[dict[str, Any]]:
    """All keywords with photo counts."""
    return search_ops.list_keywords()


@mcp.tool(annotations=READ)
def selected_photos() -> list[dict[str, Any]]:
    """Photos currently selected in Lightroom."""
    return search_ops.selected_photos()


@mcp.tool(annotations=READ)
def get_develop_settings(ids: list[int] | None = None, selected: bool = False, keys: list[str] | None = None) -> list[dict[str, Any]]:
    """Live develop settings per photo. Pass `keys` to limit the (large) result to specific settings."""
    return develop_ops.get_settings(ids, selected, keys)


@mcp.tool(annotations=READ)
def list_develop_presets() -> list[dict[str, Any]]:
    """Develop presets grouped by folder, with names and uuids."""
    return develop_ops.list_presets()


@mcp.tool(annotations=READ)
def list_plugins() -> list[dict[str, Any]]:
    """Installed Lightroom plugins with id, version, enabled state, location and Plug-in Extras menu items."""
    return plugin_ops.list_plugins()


# --- selection / organize ---------------------------------------------------------


@mcp.tool(annotations=WRITE)
def select_photos(ids: list[int]) -> dict[str, Any]:
    """Change the selection in Lightroom to these photos."""
    return search_ops.select_photos(ids)


@mcp.tool(annotations=WRITE)
def set_rating(rating: int, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Set the star rating, 0-5 (0 clears)."""
    return organize_ops.rate(rating, ids, selected)


@mcp.tool(annotations=WRITE)
def set_flag(state: str, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Set the flag: picked, rejected or unflagged."""
    return organize_ops.flag(state, ids, selected)


@mcp.tool(annotations=WRITE)
def set_color_label(color: str, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Set the color label: red, yellow, green, blue, purple or none."""
    return organize_ops.label(color, ids, selected)


@mcp.tool(annotations=WRITE)
def add_keywords(keywords: list[str], ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Add keywords to photos, creating keywords that don't exist."""
    return organize_ops.add_keywords(keywords, ids, selected)


@mcp.tool(annotations=WRITE)
def remove_keywords(keywords: list[str], ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Remove keywords from photos."""
    return organize_ops.remove_keywords(keywords, ids, selected)


@mcp.tool(annotations=WRITE)
def set_metadata(fields: dict[str, str], ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Set text metadata. Fields: title, caption, copyright, creator, headline, location, city, stateProvince, country, jobIdentifier, instructions."""
    return organize_ops.set_metadata(fields, ids, selected)


@mcp.tool(annotations=WRITE)
def create_collection(name: str, parent: str | None = None) -> dict[str, Any]:
    """Create a collection (or return the existing one). `parent` is a collection set name or id."""
    return organize_ops.create_collection(name, parent)


@mcp.tool(annotations=WRITE)
def add_to_collection(collection: str, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Add photos to a collection, given by name or id."""
    return organize_ops.add_to_collection(collection, ids, selected)


@mcp.tool(annotations=WRITE)
def remove_from_collection(collection: str, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Remove photos from a collection. The photos stay in the catalog."""
    return organize_ops.remove_from_collection(collection, ids, selected)


# --- develop -------------------------------------------------------------------


@mcp.tool(annotations=DESTRUCTIVE)
def apply_develop_settings(settings: dict[str, Any], ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Apply develop settings, e.g. {"Exposure2012": 0.5, "Contrast2012": 10}. Overwrites those settings; one undo step in Lightroom."""
    return develop_ops.set_settings(settings, ids, selected)


@mcp.tool(annotations=DESTRUCTIVE)
def copy_develop_settings(source_id: int, ids: list[int] | None = None, selected: bool = False, keys: list[str] | None = None) -> dict[str, Any]:
    """Copy develop settings from one photo onto others. Without `keys` this copies everything, including crop."""
    return develop_ops.copy_settings(source_id, ids, selected, keys)


@mcp.tool(annotations=DESTRUCTIVE)
def apply_develop_preset(preset: str, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Apply a develop preset by name or uuid."""
    return develop_ops.apply_preset(preset, ids, selected)


@mcp.tool(annotations=WRITE)
def create_virtual_copies(ids: list[int] | None = None, selected: bool = False, copy_name: str | None = None) -> dict[str, Any]:
    """Create a virtual copy of each photo and return the new copies. Changes the Lightroom selection."""
    return develop_ops.create_virtual_copies(ids, selected, copy_name)


@mcp.tool(annotations=DESTRUCTIVE)
def reset_develop_settings(ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Reset photos to default develop settings. Switches Lightroom to the Develop module and changes the selection."""
    return develop_ops.reset(ids, selected)


# --- export --------------------------------------------------------------------


@mcp.tool(annotations=WRITE)
def export_photos(
    destination: str,
    ids: list[int] | None = None,
    selected: bool = False,
    format: str = "jpeg",
    quality: int = 90,
    long_edge: int | None = None,
    color_space: str = "sRGB",
    on_collision: str = "rename",
) -> dict[str, Any]:
    """Export photos to a folder with Lightroom's renderer. Returns written file paths.

    format: jpeg | tiff | png | psd | dng | original. quality: 1-100 (JPEG). long_edge: resize in pixels.
    on_collision: rename | overwrite | skip. Large exports can take minutes.
    """
    return export_ops.export_photos(
        destination, ids, selected, format=format, quality=quality, long_edge=long_edge,
        color_space=color_space, on_collision=on_collision,
    )


# --- plugins / app ---------------------------------------------------------------


@mcp.tool(annotations=WRITE)
def install_plugin(path: str, link: bool = False, force: bool = False, restart: bool = False) -> dict[str, Any]:
    """Install a .lrplugin folder into Lightroom's Modules folder (copy, or symlink with link=true).

    Takes effect when Lightroom restarts; restart=true quits and relaunches Lightroom now.
    """
    return plugin_ops.install(path, link=link, force=force, restart=restart)


@mcp.tool(annotations=DESTRUCTIVE)
def uninstall_plugin(name: str, restart: bool = False) -> dict[str, Any]:
    """Delete a plugin from Lightroom's user Modules folder (by name, id or folder name). Plugins added through Plug-in Manager can't be removed this way."""
    return plugin_ops.uninstall(name, restart=restart)


@mcp.tool(annotations=WRITE)
def install_bridge_plugin(restart: bool = False) -> dict[str, Any]:
    """Install or update the bridge plugin that live tools depend on. restart=true quits and relaunches Lightroom."""
    return plugin_ops.install_bridge(restart=restart)


@mcp.tool(annotations=WRITE)
def reload_plugin(name: str | None = None, restart: bool = False) -> dict[str, Any]:
    """Reload the bridge plugin in place, server and handlers (no name), or reload another plugin by restarting Lightroom (restart=true required)."""
    return plugin_ops.reload(name, restart=restart)


@mcp.tool(annotations=READ)
def list_plugin_extras() -> list[dict[str, Any]]:
    """Plug-in Extras menu commands declared by installed plugins, and whether run_plugin_extra can run them."""
    return plugin_ops.list_extras()


@mcp.tool(annotations=WRITE)
def run_plugin_extra(plugin: str, title: str) -> dict[str, Any]:
    """Run a Plug-in Extras command. Only the bridge plugin's own commands can be run; Lightroom does not let plugins invoke each other's."""
    return plugin_ops.run_extra(plugin, title)


@mcp.tool(annotations=DESTRUCTIVE)
def restart_lightroom(wait_for_bridge: float = 60.0) -> dict[str, Any]:
    """Quit and relaunch Lightroom Classic. Interrupts whatever the user is doing in Lightroom; ask first."""
    return app_ops.restart(wait_for_bridge)


def run() -> None:
    mcp.run(transport="stdio", show_banner=False)
