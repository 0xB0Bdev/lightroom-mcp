from __future__ import annotations

import asyncio
import json

from fastmcp import Client
from typer.testing import CliRunner

from lightroom_mcp.cli import app
from lightroom_mcp.mcp_server import mcp

runner = CliRunner()


def test_cli_search_json(catalog_file):
    result = runner.invoke(app, ["--json", "photos", "search", "--rating", ">=3"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [p["id"] for p in data["photos"]] == [10, 13]


def test_cli_tables(catalog_file):
    result = runner.invoke(app, ["photos", "search", "--keyword", "macro"])
    assert result.exit_code == 0 and "1 of 1 photos" in result.output
    result = runner.invoke(app, ["collections", "list"])
    assert result.exit_code == 0 and "Best Of" in result.output
    result = runner.invoke(app, ["photos", "show", "10"])
    assert result.exit_code == 0 and "IMG_0001.CR2" in result.output


def test_mcp_tools(catalog_file):
    async def scenario():
        async with Client(mcp) as client:
            tools = {t.name: t for t in await client.list_tools()}
            found = await client.call_tool("search_photos", {"camera": "iphone"})
            photo = await client.call_tool("get_photo", {"photo_id": 10})
            return tools, found.data, photo.data

    tools, found, photo = asyncio.run(scenario())
    for name in ("status", "search_photos", "set_rating", "apply_develop_settings", "export_photos", "install_plugin", "restart_lightroom"):
        assert name in tools
    assert tools["search_photos"].annotations.read_only_hint is True
    assert tools["uninstall_plugin"].annotations.destructive_hint is True
    assert [p["id"] for p in found["photos"]] == [12]
    assert photo["keywords"] == ["Macro", "Travel"]
