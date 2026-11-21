"""Develop settings, presets and virtual copies (through the bridge)."""

from __future__ import annotations

from typing import Any

from .. import bridge
from . import target


def parse_assignments(pairs: list[str]) -> dict[str, Any]:
    """Turn ['Exposure2012=0.5', 'WhiteBalance=Auto'] into a settings dict with typed values."""
    settings: dict[str, Any] = {}
    for pair in pairs:
        key, sep, raw = pair.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"Expected key=value, got {pair!r}")
        raw = raw.strip()
        value: Any
        if raw.lower() in ("true", "false"):
            value = raw.lower() == "true"
        else:
            try:
                value = int(raw)
            except ValueError:
                try:
                    value = float(raw)
                except ValueError:
                    value = raw
        settings[key.strip()] = value
    return settings


def get_settings(ids: list[int] | None = None, selected: bool = False, keys: list[str] | None = None) -> list[dict[str, Any]]:
    """Current develop settings per photo, optionally limited to some keys."""
    return bridge.call("develop.get", {**target(ids, selected), "keys": keys or []})


def set_settings(settings: dict[str, Any], ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Apply develop settings, e.g. {"Exposure2012": 0.5, "Contrast2012": 10}. One undo step."""
    if not settings:
        raise ValueError("Give at least one setting.")
    return bridge.call("develop.set", {**target(ids, selected), "settings": settings})


def copy_settings(source_id: int, ids: list[int] | None = None, selected: bool = False, keys: list[str] | None = None) -> dict[str, Any]:
    """Copy develop settings from one photo to others, optionally only some keys."""
    source = target([source_id])
    return bridge.call(
        "develop.copy",
        {**target(ids, selected), "source": int(source_id), "sourceUuids": source.get("uuids", {}), "keys": keys or []},
    )


def list_presets() -> list[dict[str, Any]]:
    """Develop presets grouped by folder."""
    return bridge.call("develop.presets")


def apply_preset(preset: str, ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Apply a develop preset, given by name or UUID."""
    return bridge.call("develop.applyPreset", {**target(ids, selected), "preset": preset})


def create_virtual_copies(ids: list[int] | None = None, selected: bool = False, copy_name: str | None = None) -> dict[str, Any]:
    """Create a virtual copy of each photo. Changes the selection to the source photos."""
    return bridge.call("develop.virtualCopy", {**target(ids, selected), "copyName": copy_name})


def reset(ids: list[int] | None = None, selected: bool = False) -> dict[str, Any]:
    """Reset photos to default develop settings. Switches Lightroom to the Develop module."""
    return bridge.call("develop.reset", target(ids, selected), timeout=120)
