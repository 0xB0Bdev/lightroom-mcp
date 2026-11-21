"""lightroom-mcp: control Adobe Lightroom Classic from the command line."""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import bridge
from .core import app as app_ops
from .core import develop as develop_ops
from .core import export as export_ops
from .core import organize as organize_ops
from .core import plugins as plugin_ops
from .core import search as search_ops

app = typer.Typer(
    help="Control Adobe Lightroom Classic: search, organize, develop, export and manage plugins.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
photos_app = typer.Typer(help="Search and inspect photos; read or change the selection.", no_args_is_help=True)
collections_app = typer.Typer(help="List, create and fill collections.", no_args_is_help=True)
keywords_app = typer.Typer(help="List keywords; add them to or remove them from photos.", no_args_is_help=True)
organize_app = typer.Typer(help="Ratings, flags, color labels and text metadata.", no_args_is_help=True)
develop_app = typer.Typer(help="Develop settings, presets and virtual copies.", no_args_is_help=True)
plugins_app = typer.Typer(help="Install, remove, list and reload Lightroom plugins.", no_args_is_help=True)
app_app = typer.Typer(help="Launch, quit or restart Lightroom.", no_args_is_help=True)
app.add_typer(photos_app, name="photos")
app.add_typer(collections_app, name="collections")
app.add_typer(keywords_app, name="keywords")
app.add_typer(organize_app, name="organize")
app.add_typer(develop_app, name="develop")
app.add_typer(plugins_app, name="plugins")
app.add_typer(app_app, name="app")

console = Console()
_state = {"json": False}

Ids = typer.Argument(None, help="Photo ids (from `photos search`). Omit when using --selected.")
Selected = typer.Option(False, "--selected", "-s", help="Act on the photos selected in Lightroom.")


@app.callback()
def _root(as_json: bool = typer.Option(False, "--json", help="Print JSON instead of tables.")) -> None:
    _state["json"] = as_json


def emit(data: Any, columns: list[str] | None = None) -> None:
    """Print a result: JSON with --json, else a table for row lists and key/value lines for dicts."""
    if _state["json"]:
        print(json.dumps(data, indent=2, default=str))
        return
    if isinstance(data, list) and data and all(isinstance(r, dict) for r in data):
        cols = columns or list(data[0])
        table = Table(*cols)
        for row in data:
            table.add_row(*("" if row.get(c) is None else str(row.get(c)) for c in cols))
        console.print(table)
    elif isinstance(data, list):
        if not data:
            console.print("(none)")
        for item in data:
            console.print(str(item))
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            console.print(f"[bold]{key}[/bold]: {value}", highlight=False)
    else:
        console.print(str(data))


PHOTO_COLUMNS = ["id", "filename", "capture_time", "rating", "flag", "label", "camera", "lens", "iso", "aperture", "shutter"]


# --- top level ---------------------------------------------------------------


@app.command()
def status() -> None:
    """Show the catalog in use and whether the Lightroom bridge is reachable."""
    emit(search_ops.status())


@app.command()
def export(
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
    to: str = typer.Option(..., "--to", help="Destination folder (created if missing)."),
    format: str = typer.Option("jpeg", help="jpeg, tiff, png, psd, dng or original."),
    quality: int = typer.Option(90, help="JPEG quality, 1-100."),
    long_edge: Optional[int] = typer.Option(None, help="Resize so the long edge is this many pixels."),
    color_space: str = typer.Option("sRGB", help="sRGB, AdobeRGB or ProPhotoRGB."),
    on_collision: str = typer.Option("rename", help="When a file exists: rename, overwrite or skip."),
) -> None:
    """Export photos to a folder using Lightroom's export pipeline."""
    emit(
        export_ops.export_photos(
            to, ids, selected, format=format, quality=quality, long_edge=long_edge,
            color_space=color_space, on_collision=on_collision,
        )
    )


@app.command()
def mcp() -> None:
    """Run the MCP server over stdio so AI agents can use these commands."""
    from .mcp_server import run

    run()


# --- photos -------------------------------------------------------------------


@photos_app.command("search")
def photos_search(
    text: Optional[str] = typer.Argument(None, help="Match part of the file name."),
    rating: Optional[str] = typer.Option(None, help="e.g. 4, '>=3', '<2'."),
    flag: Optional[str] = typer.Option(None, help="picked, rejected or unflagged."),
    label: Optional[str] = typer.Option(None, help="red, yellow, green, blue, purple or none."),
    camera: Optional[str] = typer.Option(None, help="Match part of the camera model."),
    lens: Optional[str] = typer.Option(None, help="Match part of the lens name."),
    after: Optional[str] = typer.Option(None, help="Captured on or after this date (YYYY-MM-DD)."),
    before: Optional[str] = typer.Option(None, help="Captured before this date (YYYY-MM-DD)."),
    keyword: Optional[str] = typer.Option(None, help="Has this keyword."),
    collection: Optional[str] = typer.Option(None, help="In this collection (name or id)."),
    folder: Optional[str] = typer.Option(None, help="Match part of the folder path."),
    format: Optional[str] = typer.Option(None, help="File format, e.g. RAW, JPG, DNG."),
    limit: int = typer.Option(50, help="Maximum rows."),
    offset: int = typer.Option(0, help="Skip this many rows."),
) -> None:
    """Find photos in the catalog (works with Lightroom closed)."""
    result = search_ops.search_photos(
        text=text, rating=rating, flag=flag, label=label, camera=camera, lens=lens, after=after,
        before=before, keyword=keyword, collection=collection, folder=folder, format=format,
        limit=limit, offset=offset,
    )
    if _state["json"]:
        emit(result)
        return
    emit(result["photos"], PHOTO_COLUMNS)
    console.print(f"{len(result['photos'])} of {result['total']} photos", highlight=False)


@photos_app.command("show")
def photos_show(
    photo_id: int = typer.Argument(..., help="Photo id."),
    develop: bool = typer.Option(False, "--develop", help="Include all develop settings."),
) -> None:
    """Show one photo's file, EXIF, keywords, collections and caption."""
    emit(search_ops.get_photo(photo_id, include_develop=develop))


@photos_app.command("selected")
def photos_selected() -> None:
    """List the photos selected in Lightroom."""
    emit(search_ops.selected_photos(), ["id", "filename", "rating", "flag", "label", "virtual_copy"])


@photos_app.command("select")
def photos_select(ids: list[int] = typer.Argument(..., help="Photo ids to select.")) -> None:
    """Select photos in Lightroom."""
    emit(search_ops.select_photos(ids))


# --- collections / keywords ------------------------------------------------------


@collections_app.command("list")
def collections_list() -> None:
    """List collections, smart collections and collection sets."""
    emit(search_ops.list_collections(), ["id", "name", "kind", "parent_id", "photo_count"])


@collections_app.command("show")
def collections_show(collection: str = typer.Argument(..., help="Collection name or id."), limit: int = 200) -> None:
    """List the photos in a collection."""
    emit(search_ops.search_photos(collection=collection, limit=limit)["photos"], PHOTO_COLUMNS)


@collections_app.command("create")
def collections_create(
    name: str,
    parent: Optional[str] = typer.Option(None, help="Collection set to create it in (name or id)."),
) -> None:
    """Create a collection."""
    emit(organize_ops.create_collection(name, parent))


@collections_app.command("add")
def collections_add(collection: str, ids: Optional[list[int]] = Ids, selected: bool = Selected) -> None:
    """Add photos to a collection."""
    emit(organize_ops.add_to_collection(collection, ids, selected))


@collections_app.command("remove")
def collections_remove(collection: str, ids: Optional[list[int]] = Ids, selected: bool = Selected) -> None:
    """Remove photos from a collection."""
    emit(organize_ops.remove_from_collection(collection, ids, selected))


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


@keywords_app.command("list")
def keywords_list() -> None:
    """List all keywords with photo counts."""
    emit(search_ops.list_keywords(), ["id", "name", "photo_count"])


@keywords_app.command("add")
def keywords_add(
    keywords: str = typer.Argument(..., help="Comma-separated keywords."),
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
) -> None:
    """Add keywords to photos."""
    emit(organize_ops.add_keywords(_split(keywords), ids, selected))


@keywords_app.command("remove")
def keywords_remove(
    keywords: str = typer.Argument(..., help="Comma-separated keywords."),
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
) -> None:
    """Remove keywords from photos."""
    emit(organize_ops.remove_keywords(_split(keywords), ids, selected))


# --- organize ------------------------------------------------------------------


@organize_app.command("rate")
def organize_rate(
    rating: int = typer.Argument(..., help="0-5 (0 clears the rating)."),
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
) -> None:
    """Set the star rating."""
    emit(organize_ops.rate(rating, ids, selected))


@organize_app.command("flag")
def organize_flag(
    state: str = typer.Argument(..., help="picked, rejected or unflagged."),
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
) -> None:
    """Set the pick flag."""
    emit(organize_ops.flag(state, ids, selected))


@organize_app.command("label")
def organize_label(
    color: str = typer.Argument(..., help="red, yellow, green, blue, purple or none."),
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
) -> None:
    """Set the color label."""
    emit(organize_ops.label(color, ids, selected))


@organize_app.command("set-metadata")
def organize_set_metadata(
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
    field: list[str] = typer.Option(..., "--field", "-f", help="field=value, e.g. -f title='Sunset'. Repeatable."),
) -> None:
    """Set text metadata (title, caption, copyright, creator, headline, location, ...)."""
    fields = {}
    for pair in field:
        key, sep, value = pair.partition("=")
        if not sep:
            raise ValueError(f"Expected field=value, got {pair!r}")
        fields[key.strip()] = value
    emit(organize_ops.set_metadata(fields, ids, selected))


# --- develop -------------------------------------------------------------------


@develop_app.command("get")
def develop_get(
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
    keys: Optional[str] = typer.Option(None, help="Comma-separated setting names to show, e.g. Exposure2012,Temperature."),
) -> None:
    """Show current develop settings."""
    result = develop_ops.get_settings(ids, selected, _split(keys) if keys else None)
    if _state["json"]:
        emit(result)
        return
    for photo in result:
        console.print(f"[bold]{photo['id']} {photo['filename']}[/bold]", highlight=False)
        for key in sorted(photo["settings"]):
            value = photo["settings"][key]
            if not isinstance(value, (dict, list)):
                console.print(f"  {key} = {value}", highlight=False)


@develop_app.command("set")
def develop_set(
    settings: list[str] = typer.Argument(..., help="key=value pairs, e.g. Exposure2012=0.5 Contrast2012=10."),
    ids: Optional[list[int]] = typer.Option(None, "--id", "-i", help="Photo id. Repeatable."),
    selected: bool = Selected,
) -> None:
    """Apply develop settings to photos (one undo step)."""
    emit(develop_ops.set_settings(develop_ops.parse_assignments(settings), ids, selected))


@develop_app.command("copy")
def develop_copy(
    source: int = typer.Argument(..., help="Photo id to copy settings from."),
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
    keys: Optional[str] = typer.Option(None, help="Only copy these comma-separated settings."),
) -> None:
    """Copy develop settings from one photo to others."""
    emit(develop_ops.copy_settings(source, ids, selected, _split(keys) if keys else None))


@develop_app.command("presets")
def develop_presets() -> None:
    """List develop presets."""
    folders = develop_ops.list_presets()
    if _state["json"]:
        emit(folders)
        return
    emit([{"folder": f["folder"], **p} for f in folders for p in f["presets"]], ["folder", "name", "uuid"])


@develop_app.command("apply-preset")
def develop_apply_preset(
    preset: str = typer.Argument(..., help="Preset name or uuid."),
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
) -> None:
    """Apply a develop preset."""
    emit(develop_ops.apply_preset(preset, ids, selected))


@develop_app.command("virtual-copy")
def develop_virtual_copy(
    ids: Optional[list[int]] = Ids,
    selected: bool = Selected,
    name: Optional[str] = typer.Option(None, help="Copy name."),
) -> None:
    """Create virtual copies."""
    emit(develop_ops.create_virtual_copies(ids, selected, name))


@develop_app.command("reset")
def develop_reset(ids: Optional[list[int]] = Ids, selected: bool = Selected) -> None:
    """Reset develop settings (switches Lightroom to the Develop module)."""
    emit(develop_ops.reset(ids, selected))


# --- plugins -------------------------------------------------------------------


@plugins_app.command("list")
def plugins_list() -> None:
    """List plugins in Lightroom's Modules folders and those added in Plug-in Manager."""
    emit(plugin_ops.list_plugins(), ["name", "id", "version", "enabled", "source", "exists", "path"])


@plugins_app.command("install")
def plugins_install(
    path: str = typer.Argument(..., help="Path to a .lrplugin folder."),
    link: bool = typer.Option(False, "--link", help="Symlink instead of copying (handy while developing)."),
    force: bool = typer.Option(False, "--force", help="Replace an installed plugin with the same folder name."),
    restart: bool = typer.Option(False, "--restart", help="Restart Lightroom so it loads now."),
) -> None:
    """Install a plugin into Lightroom's Modules folder."""
    emit(plugin_ops.install(path, link=link, force=force, restart=restart))


@plugins_app.command("uninstall")
def plugins_uninstall(
    name: str = typer.Argument(..., help="Plugin name, id or folder name."),
    restart: bool = typer.Option(False, "--restart", help="Restart Lightroom afterwards."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask for confirmation."),
) -> None:
    """Remove a plugin that was installed into the Modules folder."""
    if not yes:
        typer.confirm(f"Remove plugin {name!r} from Lightroom's Modules folder?", abort=True)
    emit(plugin_ops.uninstall(name, restart=restart))


@plugins_app.command("bridge-install")
def plugins_bridge_install(
    link: bool = typer.Option(False, "--link", help="Symlink to this package's copy instead of copying."),
    restart: bool = typer.Option(False, "--restart", help="Restart Lightroom so it loads now."),
) -> None:
    """Install or update the bridge plugin this tool needs for live commands."""
    emit(plugin_ops.install_bridge(link=link, restart=restart))


@plugins_app.command("reload")
def plugins_reload(
    name: Optional[str] = typer.Argument(None, help="Plugin to reload. Omit for the bridge plugin."),
    restart: bool = typer.Option(False, "--restart", help="Restart Lightroom (required for other plugins)."),
) -> None:
    """Reload the bridge plugin in place (server and handlers), or restart Lightroom to reload another plugin."""
    emit(plugin_ops.reload(name, restart=restart))


@plugins_app.command("extras")
def plugins_extras() -> None:
    """List Plug-in Extras menu commands declared by installed plugins."""
    emit(plugin_ops.list_extras(), ["plugin", "menu", "title", "runnable"])


@plugins_app.command("run-extra")
def plugins_run_extra(plugin: str, title: str) -> None:
    """Run a Plug-in Extras command (only the bridge plugin's own commands can be run)."""
    emit(plugin_ops.run_extra(plugin, title))


# --- app -----------------------------------------------------------------------


@app_app.command("launch")
def app_launch(wait: float = typer.Option(0, help="Seconds to wait for the bridge to answer.")) -> None:
    """Start Lightroom."""
    emit(app_ops.launch(wait))


@app_app.command("quit")
def app_quit() -> None:
    """Quit Lightroom."""
    emit(app_ops.quit())


@app_app.command("restart")
def app_restart(wait: float = typer.Option(60, help="Seconds to wait for the bridge to answer.")) -> None:
    """Quit and relaunch Lightroom."""
    emit(app_ops.restart(wait))


def main() -> None:
    if sys.platform != "darwin":
        print("Error: lightroom-mcp only runs on macOS.", file=sys.stderr)
        sys.exit(1)
    try:
        app()
    except (bridge.BridgeError, ValueError, LookupError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
