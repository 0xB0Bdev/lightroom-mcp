"""Ratings, flags, labels, keywords, metadata and collections (all through the bridge)."""

from __future__ import annotations

from typing import Any

from .. import bridge
from . import target

FLAGS = {"picked": 1, "pick": 1, "rejected": -1, "reject": -1, "unflagged": 0, "none": 0}
LABELS = ("red", "yellow", "green", "blue", "purple", "none")
METADATA_FIELDS = (
    "title",
    "caption",
    "copyright",
    "creator",
    "headline",
    "location",
    "city",
    "stateProvince",
    "country",
    "jobIdentifier",
    "instructions",
)


def rate(rating: int, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Set the star rating (0-5; 0 clears it)."""
    if not 0 <= rating <= 5:
        raise ValueError("rating must be 0-5")
    return bridge.call("organize.rate", {**target(ids, selected), "rating": rating})


def flag(state: str, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Set the flag: picked, rejected or unflagged."""
    if state.lower() not in FLAGS:
        raise ValueError("flag must be one of: picked, rejected, unflagged")
    return bridge.call("organize.flag", {**target(ids, selected), "pick": FLAGS[state.lower()]})


def label(color: str, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Set the color label: red, yellow, green, blue, purple or none."""
    if color.lower() not in LABELS:
        raise ValueError(f"label must be one of: {', '.join(LABELS)}")
    return bridge.call("organize.label", {**target(ids, selected), "label": color.lower()})


def add_keywords(keywords: list[str], ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Add keywords, creating any that don't exist yet."""
    if not keywords:
        raise ValueError("Give at least one keyword.")
    return bridge.call("organize.addKeywords", {**target(ids, selected), "keywords": keywords})


def remove_keywords(keywords: list[str], ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Remove keywords from photos (the keywords themselves stay in the catalog)."""
    if not keywords:
        raise ValueError("Give at least one keyword.")
    return bridge.call("organize.removeKeywords", {**target(ids, selected), "keywords": keywords})


def set_metadata(fields: dict[str, str], ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Set text metadata such as title, caption or copyright."""
    unknown = sorted(set(fields) - set(METADATA_FIELDS))
    if unknown:
        raise ValueError(f"Unsupported field(s): {', '.join(unknown)}. Use: {', '.join(METADATA_FIELDS)}")
    if not fields:
        raise ValueError("Give at least one field=value.")
    return bridge.call("organize.setMetadata", {**target(ids, selected), "fields": fields})


def create_collection(name: str, parent: str | None = None) -> dict[str, Any]:
    """Create a collection (returns the existing one if the name is taken). `parent` is a collection set name or id."""
    return bridge.call("collections.create", {"name": name, "parent": parent})


def add_to_collection(collection: str, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Add photos to a collection, given by name or id."""
    return bridge.call("collections.add", {**target(ids, selected), "collection": collection})


def remove_from_collection(collection: str, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Remove photos from a collection (the photos stay in the catalog)."""
    return bridge.call("collections.remove", {**target(ids, selected), "collection": collection})
