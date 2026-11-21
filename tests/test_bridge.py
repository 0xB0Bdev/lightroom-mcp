"""Bridge client against a fake plugin: a listening socket plus reply files, like the real one."""

from __future__ import annotations

import json
import socket
import threading

import pytest

from lightroom_mcp import bridge
from lightroom_mcp.core import develop, organize, target


class FakePlugin:
    """Accepts clients on one port; answers each request by writing its reply file, like the real plugin."""

    def __init__(self, handler, response_dir):
        self.handler = handler
        self.response_dir = response_dir
        self.requests: list[dict] = []
        self.drop_connections = 0
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            if self.drop_connections > 0:
                self.drop_connections -= 1
                conn.close()  # accepted, then dropped unread, as Lightroom does while re-listening
                continue
            buffer = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, _, buffer = buffer.partition(b"\n")
                    request = json.loads(line)
                    self.requests.append(request)
                    conn.sendall(b"ok\r\n")  # Lightroom acknowledges each line this way
                    reply = self.handler(request)
                    if reply is not None:
                        (self.response_dir / f"{request['reply']}.json").write_text(json.dumps(reply))
            conn.close()

    def close(self):
        self.server.close()


@pytest.fixture
def fake(monkeypatch, tmp_path):
    plugins = []
    responses = tmp_path / "responses"
    responses.mkdir()

    def make(handler):
        plugin = FakePlugin(handler, responses)
        plugins.append(plugin)
        monkeypatch.setattr(bridge, "_shared", bridge.Bridge(port=plugin.port, response_dir=responses))
        return plugin

    yield make
    if bridge._shared:
        bridge._shared.close()
    for plugin in plugins:
        plugin.close()


def test_call_returns_result(fake):
    plugin = fake(lambda r: {"id": r["id"], "ok": True, "result": {"echo": r["params"]}})
    assert bridge.call("ping", {"a": 1}) == {"echo": {"a": 1}}
    assert bridge.call("ping") == {"echo": {}}
    assert [r["command"] for r in plugin.requests] == ["ping", "ping"]
    assert plugin.requests[0]["reply"] != plugin.requests[1]["reply"]
    assert list(plugin.response_dir.iterdir()) == []  # replies are removed once read


def test_error_response_raises(fake):
    fake(lambda r: {"id": r["id"], "ok": False, "error": "No photo with id 7"})
    with pytest.raises(bridge.BridgeError, match="No photo with id 7"):
        bridge.call("organize.rate", {"ids": [7], "rating": 3})


def test_connection_is_released_between_calls(fake):
    fake(lambda r: {"id": r["id"], "ok": True, "result": "pong"})
    assert bridge.call("ping") == "pong"
    assert bridge._shared._sock is None  # the plugin serves one client at a time
    assert bridge.call("ping") == "pong"


def test_resends_when_the_connection_drops_before_the_acknowledgement(fake):
    plugin = fake(lambda r: {"id": r["id"], "ok": True, "result": "pong"})
    plugin.drop_connections = 2
    assert bridge.call("ping") == "pong"
    assert len(plugin.requests) == 1


def test_timeout(fake):
    fake(lambda r: None)
    with pytest.raises(bridge.BridgeError, match="did not answer"):
        bridge.call("export.run", timeout=0.3)


def test_unreachable(monkeypatch):
    server = socket.create_server(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.close()
    client = bridge.Bridge(port=port)
    with pytest.raises(bridge.BridgeUnavailable):
        client.connect(wait=0.3)


def test_core_builds_bridge_params(fake, catalog_file):
    plugin = fake(lambda r: {"id": r["id"], "ok": True, "result": {"updated": 2}})
    organize.rate(4, [10, 11])
    organize.flag("rejected", selected=True)
    develop.set_settings(develop.parse_assignments(["Exposure2012=0.5", "Contrast2012=10", "WhiteBalance=Auto"]), [10])
    sent = [(r["command"], r["params"]) for r in plugin.requests]
    assert sent == [
        ("organize.rate", {"ids": [10, 11], "uuids": {"10": "UUID-10", "11": "UUID-11"}, "rating": 4}),
        ("organize.flag", {"selected": True, "pick": -1}),
        ("develop.set", {"ids": [10], "uuids": {"10": "UUID-10"}, "settings": {"Exposure2012": 0.5, "Contrast2012": 10, "WhiteBalance": "Auto"}}),
    ]


def test_ids_missing_from_catalog_are_still_sent(fake, catalog_file):
    plugin = fake(lambda r: {"id": r["id"], "ok": True, "result": {}})
    organize.rate(1, [999])
    assert plugin.requests[0]["params"] == {"ids": [999], "rating": 1}


def test_validation_happens_before_the_bridge():
    with pytest.raises(ValueError):
        organize.rate(6, [1])
    with pytest.raises(ValueError):
        organize.label("pink", [1])
    with pytest.raises(ValueError):
        organize.set_metadata({"nonsense": "x"}, [1])
    with pytest.raises(ValueError):
        target(None, False)
    with pytest.raises(ValueError):
        target([1], True)
