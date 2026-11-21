from __future__ import annotations

import pytest

from lightroom_mcp import config


def lightroom_folder(monkeypatch, tmp_path, *names):
    folder = tmp_path / "Pictures/Lightroom"
    folder.mkdir(parents=True)
    for name in names:
        (folder / name).touch()
    monkeypatch.delenv("LIGHTROOM_CATALOG", raising=False)
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "DEFAULT_CATALOG", folder / "Lightroom Catalog.lrcat")
    return folder


def test_catalog_path_uses_the_only_catalog(monkeypatch, tmp_path):
    folder = lightroom_folder(monkeypatch, tmp_path, "Lightroom Catalog-v13-3.lrcat")
    assert config.catalog_path() == folder / "Lightroom Catalog-v13-3.lrcat"


def test_catalog_path_with_several_catalogs_names_them(monkeypatch, tmp_path):
    lightroom_folder(monkeypatch, tmp_path, "Lightroom Catalog-v12.lrcat", "Lightroom Catalog-v13-3.lrcat")
    with pytest.raises(FileNotFoundError) as exc:
        config.catalog_path()
    message = str(exc.value)
    assert "Found 2 Lightroom catalogs" in message
    assert "Lightroom Catalog-v12.lrcat" in message and "Lightroom Catalog-v13-3.lrcat" in message
    assert "LIGHTROOM_CATALOG" in message


def test_catalog_path_with_no_catalog(monkeypatch, tmp_path):
    lightroom_folder(monkeypatch, tmp_path)
    with pytest.raises(FileNotFoundError, match="No Lightroom catalog found"):
        config.catalog_path()


def test_bridge_port_from_env(monkeypatch):
    monkeypatch.setenv("LIGHTROOM_BRIDGE_PORT", "60001")
    assert config.bridge_port() == 60001


@pytest.mark.parametrize("value", ["abc", "0", "65536", "99999", "-1", "1.5"])
def test_invalid_bridge_port_names_the_setting(monkeypatch, value):
    monkeypatch.setenv("LIGHTROOM_BRIDGE_PORT", value)
    with pytest.raises(ValueError, match=f"LIGHTROOM_BRIDGE_PORT .* got '{value}'"):
        config.bridge_port()
