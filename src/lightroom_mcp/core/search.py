"""Search and inspect: catalog reads, plus selection through the bridge."""

from __future__ import annotations

from typing import Any

from .. import bridge, catalog
from . import target


def status() -> dict[str, Any]:
    """Catalog summary, and live Lightroom state when the bridge is reachable."""
    out: dict[str, Any] = {}
    try:
        out.update(catalog.summary())
    except (FileNotFoundError, OSError) as exc:
        out["catalog_error"] = str(exc)
    try:
        out["bridge"] = bridge.call("status", timeout=5)
        out["bridge_connected"] = True
    except bridge.BridgeError as exc:
        out["bridge_connected"] = False
        out["bridge_error"] = str(exc)
    return out


search_photos = catalog.search_photos
get_photo = catalog.get_photo
list_collections = catalog.list_collections
list_keywords = catalog.list_keywords


def selected_photos() -> list[dict[str, Any]]:
    """Photos currently selected in Lightroom."""
    return bridge.call("photos.selected")


def select_photos(ids: list[int]) -> dict[str, Any]:
    """Make these photos the selection in Lightroom (the first becomes the active photo)."""
    if not ids:
        raise ValueError("Give at least one photo id.")
    return bridge.call("photos.select", target(ids))
