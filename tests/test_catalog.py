from __future__ import annotations

import pytest

from lightroom_mcp import catalog, luatable


def ids(result):
    return [p["id"] for p in result["photos"]]


def test_search_all_sorted_by_capture_time(catalog_file):
    result = catalog.search_photos()
    assert result["total"] == 4
    assert ids(result) == [10, 13, 11, 12]


def test_photo_fields(catalog_file):
    photo = catalog.search_photos(text="IMG_0001", format="raw", rating="5")["photos"][0]
    assert photo["filename"] == "IMG_0001.CR2"
    assert photo["path"] == "/Photos/2026/trip/IMG_0001.CR2"
    assert photo["camera"] == "Canon EOS 6D"
    assert photo["aperture"] == 11.0
    assert photo["shutter"] == "1/2"
    assert photo["iso"] == 100
    assert photo["flag"] == "picked"
    assert photo["virtual_copy"] is False


def test_long_exposure_formatting(catalog_file):
    assert catalog.get_photo(12)["shutter"] == "2.0s"
    assert catalog.get_photo(11)["shutter"] == "1/120"


@pytest.mark.parametrize(
    "filters, expected",
    [
        ({"rating": ">=3"}, [10, 13]),
        ({"rating": "0"}, [12]),
        ({"rating": "<3"}, [11, 12]),
        ({"flag": "rejected"}, [11]),
        ({"flag": "unflagged"}, [13, 12]),
        ({"label": "red"}, [10]),
        ({"label": "none"}, [13, 11, 12]),
        ({"camera": "iphone"}, [12]),
        ({"lens": "macro"}, [10, 11]),
        ({"after": "2026-02-01"}, [11, 12]),
        ({"before": "2026-02-01"}, [10, 13]),
        ({"keyword": "TRAVEL"}, [10, 11]),
        ({"collection": "best of"}, [10, 12]),
        ({"collection": "20"}, [10, 12]),
        ({"folder": "trip"}, [10, 13, 11, 12]),
        ({"format": "jpg"}, [12]),
        ({"text": "100%"}, [12]),
        ({"text": "_"}, [10, 13, 11, 12]),
        ({"rating": ">=2", "keyword": "travel"}, [10, 11]),
    ],
)
def test_filters(catalog_file, filters, expected):
    assert ids(catalog.search_photos(**filters)) == expected


def test_paging(catalog_file):
    page = catalog.search_photos(limit=2, offset=1)
    assert page["total"] == 4
    assert ids(page) == [13, 11]


def test_bad_filters(catalog_file):
    with pytest.raises(ValueError):
        catalog.search_photos(rating="great")
    with pytest.raises(ValueError):
        catalog.search_photos(flag="maybe")


def test_get_photo_details(catalog_file):
    photo = catalog.get_photo(10)
    assert photo["keywords"] == ["Macro", "Travel"]
    assert photo["collections"] == ["Best Of"]
    assert photo["caption"] == "A caption"
    assert photo["develop"]["Exposure2012"] == 0.5
    assert photo["develop"]["ToneCurvePV2012"] == [0, 0, 255, 255]
    assert photo["develop"]["Look"] == {"Name": "Vivid", "Amount": 1}
    assert catalog.get_photo(13)["virtual_copy"] is True
    with pytest.raises(LookupError):
        catalog.get_photo(999)


def test_collections_and_keywords(catalog_file):
    collections = {c["name"]: c for c in catalog.list_collections()}
    assert set(collections) == {"Best Of", "Five Stars"}
    assert collections["Best Of"]["photo_count"] == 2
    assert collections["Five Stars"]["kind"] == "smart"
    assert [(k["name"], k["photo_count"]) for k in catalog.list_keywords()] == [("Macro", 1), ("Travel", 2)]
    assert catalog.summary()["photos"] == 4


def test_catalog_is_opened_read_only(catalog_file):
    with catalog.connect() as conn:
        with pytest.raises(Exception, match="readonly"):
            conn.execute("UPDATE Adobe_images SET rating = 1")


@pytest.mark.parametrize("name", ["Catalog #2.lrcat", "Catalog 50%25.lrcat", "What?.lrcat"])
def test_catalog_path_with_uri_characters(catalog_file, monkeypatch, name):
    path = catalog_file.rename(catalog_file.with_name(name))
    monkeypatch.setenv("LIGHTROOM_CATALOG", str(path))
    assert catalog.summary()["photos"] == 4
    with catalog.connect() as conn:
        with pytest.raises(Exception, match="readonly"):
            conn.execute("UPDATE Adobe_images SET rating = 1")
    assert [p.name for p in path.parent.iterdir()] == [name]  # nothing created beside it


def test_luatable_prefs_shape():
    text = 't = {\n\t["/a/b.lrplugin"] = "/a/b.lrplugin",\n\t["/c d/e.lrplugin"] = true,\n}\n'
    assert luatable.parse(text) == {"/a/b.lrplugin": "/a/b.lrplugin", "/c d/e.lrplugin": True}
    assert luatable.parse("t = {\n}\n") == []
    assert luatable.parse('{ a = -1.5, b = "x\\"y", 3, nil }') == {"a": -1.5, "b": 'x"y', 1: 3, 2: None}
