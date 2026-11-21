"""Export photos through Lightroom's export pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import bridge
from . import target

FORMATS = {"jpeg": "JPEG", "jpg": "JPEG", "tiff": "TIFF", "tif": "TIFF", "png": "PNG", "psd": "PSD", "dng": "DNG", "original": "ORIGINAL"}
COLLISIONS = ("rename", "overwrite", "skip")


def export_photos(
    destination: str,
    ids: list[int] | None = None,
    selected: bool = False,
    format: str = "jpeg",
    quality: int = 90,
    long_edge: int | None = None,
    color_space: str = "sRGB",
    on_collision: str = "rename",
    timeout: float = 600.0,
) -> dict[str, Any]:
    """Export photos to a folder. Returns the written file paths and any per-photo errors."""
    fmt = FORMATS.get(format.lower())
    if fmt is None:
        raise ValueError(f"format must be one of: {', '.join(sorted(set(FORMATS)))}")
    if on_collision not in COLLISIONS:
        raise ValueError(f"on_collision must be one of: {', '.join(COLLISIONS)}")
    if not 1 <= quality <= 100:
        raise ValueError("quality must be 1-100")
    dest = Path(destination).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    return bridge.call(
        "export.run",
        {
            **target(ids, selected),
            "destination": str(dest),
            "format": fmt,
            "quality": quality / 100,
            "longEdge": long_edge,
            "colorSpace": color_space,
            "collision": on_collision,
        },
        timeout=timeout,
    )
