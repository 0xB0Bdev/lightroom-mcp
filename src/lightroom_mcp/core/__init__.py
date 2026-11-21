"""Operations shared by the CLI and the MCP server. Each function returns JSON-friendly data."""

from __future__ import annotations

import sqlite3
from typing import Any

from .. import catalog


def target(ids: list[int] | None, selected: bool = False) -> dict[str, Any]:
    """Bridge params naming which photos to act on: explicit catalog ids, or the current selection."""
    if ids and selected:
        raise ValueError("Give photo ids or use the current selection, not both.")
    if ids:
        ids = [int(i) for i in ids]
        params: dict[str, Any] = {"ids": ids}
        # The SDK finds photos by UUID, not by id; without UUIDs the plugin scans the catalog.
        try:
            uuids = catalog.photo_uuids(ids)
        except (OSError, sqlite3.Error):
            uuids = {}
        if uuids:
            params["uuids"] = uuids
        return params
    if selected:
        return {"selected": True}
    raise ValueError("No photos given: pass photo ids or use the current selection.")
