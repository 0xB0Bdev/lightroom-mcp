"""Read-only access to a Lightroom Classic catalog (.lrcat is SQLite).

Nothing in this module ever writes to the catalog. Changes go through the bridge plugin.
"""

from __future__ import annotations

import re
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import config, luatable

_PHOTO_SELECT = """
SELECT i.id_local AS id,
       f.baseName || '.' || f.extension AS filename,
       rf.absolutePath || fo.pathFromRoot || f.baseName || '.' || f.extension AS path,
       i.captureTime AS capture_time,
       CAST(COALESCE(i.rating, 0) AS INTEGER) AS rating,
       CAST(COALESCE(i.pick, 0) AS INTEGER) AS pick,
       LOWER(COALESCE(i.colorLabels, '')) AS label,
       i.fileFormat AS format,
       i.fileWidth AS width,
       i.fileHeight AS height,
       i.masterImage AS master_id,
       i.copyName AS copy_name,
       cm.value AS camera,
       l.value AS lens,
       e.aperture AS aperture_apex,
       e.shutterSpeed AS shutter_apex,
       e.isoSpeedRating AS iso,
       e.focalLength AS focal_length
FROM Adobe_images i
JOIN AgLibraryFile f ON f.id_local = i.rootFile
JOIN AgLibraryFolder fo ON fo.id_local = f.folder
JOIN AgLibraryRootFolder rf ON rf.id_local = fo.rootFolder
LEFT JOIN AgHarvestedExifMetadata e ON e.image = i.id_local
LEFT JOIN AgInternedExifCameraModel cm ON cm.id_local = e.cameraModelRef
LEFT JOIN AgInternedExifLens l ON l.id_local = e.lensRef
"""

_FLAGS = {"picked": 1, "pick": 1, "flagged": 1, "rejected": -1, "reject": -1, "unflagged": 0, "none": 0}
_FLAG_NAMES = {1: "picked", -1: "rejected", 0: "unflagged"}

_USER_COLLECTION_TYPES = (
    "com.adobe.ag.library.collection",
    "com.adobe.ag.library.smart_collection",
    "com.adobe.ag.library.group",
)


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open the catalog read-only. If Lightroom holds it locked, query a temporary copy."""
    path = path or config.catalog_path()
    if not path.exists():
        raise FileNotFoundError(f"Catalog not found: {path}")
    tmpdir: str | None = None
    # as_uri() percent-encodes characters such as # ? % that would otherwise end the path.
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        conn.execute("SELECT 1 FROM Adobe_images LIMIT 1").fetchone()
    except sqlite3.OperationalError as exc:
        conn.close()
        if "locked" not in str(exc) and "busy" not in str(exc):
            raise
        tmpdir = tempfile.mkdtemp(prefix="lrcat-")
        copy = Path(tmpdir) / path.name
        shutil.copy2(path, copy)
        wal = path.with_name(path.name + "-wal")
        if wal.exists():
            shutil.copy2(wal, copy.with_name(copy.name + "-wal"))
        conn = sqlite3.connect(copy)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def _photo(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    ap, sh = d.pop("aperture_apex"), d.pop("shutter_apex")
    d["aperture"] = round(2 ** (ap / 2), 1) if ap is not None else None
    if sh is None:
        d["shutter"] = None
    else:
        seconds = 2 ** (-sh)
        d["shutter"] = f"1/{round(1 / seconds)}" if seconds < 1 else f"{round(seconds, 1)}s"
    for key in ("width", "height", "iso"):
        if d[key] is not None:
            d[key] = int(d[key])
    if d["focal_length"] is not None:
        d["focal_length"] = round(d["focal_length"], 1)
    d["flag"] = _FLAG_NAMES.get(d.pop("pick"), "unflagged")
    d["virtual_copy"] = d["master_id"] is not None
    return d


def _rating_clause(expr: str) -> tuple[str, int]:
    m = re.fullmatch(r"\s*(>=|<=|=|==|>|<)?\s*([0-5])\s*", expr)
    if not m:
        raise ValueError(f"Invalid rating filter {expr!r}; use e.g. '3', '>=3', '<2'")
    op = m.group(1) or "="
    return f"COALESCE(i.rating, 0) {'=' if op == '==' else op} ?", int(m.group(2))


def search_photos(
    *,
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
    path: Path | None = None,
) -> dict[str, Any]:
    """Find photos. Text filters are case-insensitive substring matches; dates are ISO (YYYY-MM-DD)."""
    where: list[str] = []
    args: list[Any] = []

    def like(column: str, value: str) -> None:
        where.append(f"{column} LIKE ? ESCAPE '\\'")
        args.append("%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")

    if text:
        like("(f.baseName || '.' || f.extension)", text)
    if rating:
        clause, value = _rating_clause(rating)
        where.append(clause)
        args.append(value)
    if flag:
        if flag.lower() not in _FLAGS:
            raise ValueError("flag must be one of: picked, rejected, unflagged")
        where.append("COALESCE(i.pick, 0) = ?")
        args.append(_FLAGS[flag.lower()])
    if label:
        if label.lower() == "none":
            where.append("COALESCE(i.colorLabels, '') = ''")
        else:
            where.append("LOWER(i.colorLabels) = ?")
            args.append(label.lower())
    if camera:
        like("cm.value", camera)
    if lens:
        like("l.value", lens)
    if after:
        where.append("i.captureTime >= ?")
        args.append(after)
    if before:
        where.append("i.captureTime < ?")
        args.append(before)
    if keyword:
        where.append(
            "EXISTS (SELECT 1 FROM AgLibraryKeywordImage ki JOIN AgLibraryKeyword k ON k.id_local = ki.tag"
            " WHERE ki.image = i.id_local AND k.lc_name = ?)"
        )
        args.append(keyword.lower())
    if collection:
        where.append(
            "EXISTS (SELECT 1 FROM AgLibraryCollectionImage ci JOIN AgLibraryCollection c"
            " ON c.id_local = ci.collection WHERE ci.image = i.id_local"
            " AND (LOWER(c.name) = ? OR CAST(c.id_local AS TEXT) = ?))"
        )
        args += [collection.lower(), collection]
    if folder:
        like("(rf.absolutePath || fo.pathFromRoot)", folder)
    if format:
        where.append("LOWER(i.fileFormat) = ?")
        args.append(format.lower())

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    with connect(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM ({_PHOTO_SELECT}{where_sql})", args
        ).fetchone()[0]
        rows = conn.execute(
            f"{_PHOTO_SELECT}{where_sql} ORDER BY i.captureTime, i.id_local LIMIT ? OFFSET ?",
            [*args, limit, offset],
        ).fetchall()
    return {"total": total, "offset": offset, "photos": [_photo(r) for r in rows]}


def get_photo(photo_id: int, *, include_develop: bool = True, path: Path | None = None) -> dict[str, Any]:
    """Full details for one photo: file, EXIF, keywords, collections, caption and develop settings."""
    with connect(path) as conn:
        row = conn.execute(f"{_PHOTO_SELECT} WHERE i.id_local = ?", [photo_id]).fetchone()
        if row is None:
            raise LookupError(f"No photo with id {photo_id}")
        photo = _photo(row)
        photo["keywords"] = [
            r[0]
            for r in conn.execute(
                "SELECT k.name FROM AgLibraryKeywordImage ki JOIN AgLibraryKeyword k ON k.id_local = ki.tag"
                " WHERE ki.image = ? ORDER BY k.lc_name",
                [photo_id],
            )
        ]
        photo["collections"] = [
            r[0]
            for r in conn.execute(
                "SELECT c.name FROM AgLibraryCollectionImage ci JOIN AgLibraryCollection c"
                " ON c.id_local = ci.collection WHERE ci.image = ? ORDER BY c.name",
                [photo_id],
            )
        ]
        iptc = conn.execute(
            "SELECT caption, copyright FROM AgLibraryIPTC WHERE image = ?", [photo_id]
        ).fetchone()
        photo["caption"] = iptc["caption"] if iptc else None
        photo["copyright"] = iptc["copyright"] if iptc else None
        if include_develop:
            dev = conn.execute(
                "SELECT text, processVersion, hasDevelopAdjustmentsEx FROM Adobe_imageDevelopSettings"
                " WHERE image = ?",
                [photo_id],
            ).fetchone()
            photo["develop"] = None
            if dev and dev["text"]:
                try:
                    photo["develop"] = luatable.parse(dev["text"])
                except ValueError:
                    photo["develop"] = {"_unparsed": True}
    return photo


def photo_uuids(ids: list[int], *, path: Path | None = None) -> dict[str, str]:
    """Map photo ids to Lightroom's UUIDs, which is what the SDK can look photos up by."""
    if not ids:
        return {}
    with connect(path) as conn:
        rows = conn.execute(
            f"SELECT id_local, id_global FROM Adobe_images WHERE id_local IN ({','.join('?' * len(ids))})",
            [int(i) for i in ids],
        ).fetchall()
    return {str(r[0]): r[1] for r in rows if r[1]}


def list_collections(*, include_smart: bool = True, path: Path | None = None) -> list[dict[str, Any]]:
    """User collections, smart collections and collection sets."""
    kinds = {
        "com.adobe.ag.library.collection": "collection",
        "com.adobe.ag.library.smart_collection": "smart",
        "com.adobe.ag.library.group": "set",
    }
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT c.id_local AS id, c.name, c.creationId, c.parent AS parent_id,"
            " (SELECT COUNT(*) FROM AgLibraryCollectionImage ci WHERE ci.collection = c.id_local) AS photo_count"
            f" FROM AgLibraryCollection c WHERE c.creationId IN ({','.join('?' * len(_USER_COLLECTION_TYPES))})"
            " ORDER BY c.name",
            _USER_COLLECTION_TYPES,
        ).fetchall()
    out = []
    for r in rows:
        kind = kinds[r["creationId"]]
        if kind == "smart" and not include_smart:
            continue
        out.append(
            {
                "id": r["id"],
                "name": r["name"],
                "kind": kind,
                "parent_id": r["parent_id"],
                "photo_count": None if kind != "collection" else r["photo_count"],
            }
        )
    return out


def list_keywords(*, path: Path | None = None) -> list[dict[str, Any]]:
    """All keywords with how many photos carry each."""
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT k.id_local AS id, k.name, k.parent AS parent_id,"
            " (SELECT COUNT(*) FROM AgLibraryKeywordImage ki WHERE ki.tag = k.id_local) AS photo_count"
            " FROM AgLibraryKeyword k WHERE k.name IS NOT NULL ORDER BY k.lc_name"
        ).fetchall()
    return [dict(r) for r in rows]


def summary(*, path: Path | None = None) -> dict[str, Any]:
    """Catalog path plus photo, collection and keyword counts."""
    p = path or config.catalog_path()
    with connect(p) as conn:
        photos = conn.execute("SELECT COUNT(*) FROM Adobe_images").fetchone()[0]
        keywords = conn.execute(
            "SELECT COUNT(*) FROM AgLibraryKeyword WHERE name IS NOT NULL"
        ).fetchone()[0]
        collections = conn.execute(
            "SELECT COUNT(*) FROM AgLibraryCollection WHERE creationId = 'com.adobe.ag.library.collection'"
        ).fetchone()[0]
    return {"catalog": str(p), "photos": photos, "collections": collections, "keywords": keywords}
