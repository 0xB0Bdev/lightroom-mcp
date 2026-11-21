from __future__ import annotations

import pytest

from lightroom_mcp import config


def test_bridge_port_from_env(monkeypatch):
    monkeypatch.setenv("LIGHTROOM_BRIDGE_PORT", "60001")
    assert config.bridge_port() == 60001


@pytest.mark.parametrize("value", ["abc", "0", "65536", "99999", "-1", "1.5"])
def test_invalid_bridge_port_names_the_setting(monkeypatch, value):
    monkeypatch.setenv("LIGHTROOM_BRIDGE_PORT", value)
    with pytest.raises(ValueError, match=f"LIGHTROOM_BRIDGE_PORT .* got '{value}'"):
        config.bridge_port()
