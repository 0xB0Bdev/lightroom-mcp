"""Client for the LightroomBridge plugin.

Requests are newline-delimited JSON written to the plugin's localhost socket. Each
request names a reply token, and the plugin answers by writing <token>.json into a
shared responses folder. (Lightroom's sockets are one-directional, and its sending
mode can't cope with clients coming and going, so replies don't use a socket.)
"""

from __future__ import annotations

import itertools
import json
import re
import select
import socket
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from . import config


class BridgeError(RuntimeError):
    """The plugin reported an error for a command."""


class BridgeUnavailable(BridgeError):
    """Could not reach the plugin at all."""


_UNAVAILABLE = (
    "Can't reach the Lightroom bridge. Make sure Lightroom Classic is running and the bridge "
    "plugin is installed (`lightroom-mcp plugins bridge-install --restart`)."
)


class Bridge:
    def __init__(self, host: str = "127.0.0.1", port: int | None = None, response_dir: Path | None = None):
        self.host = host
        self.port = port or config.bridge_port()
        self.response_dir = Path(response_dir or config.RESPONSE_DIR)
        self._sock: socket.socket | None = None
        self._session = uuid.uuid4().hex
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def connect(self, wait: float = 3.0) -> None:
        """Connect, retrying briefly (the plugin stops listening for a moment after each disconnect)."""
        deadline = time.monotonic() + wait
        while True:
            try:
                self._sock = socket.create_connection((self.host, self.port), timeout=1)
                return
            except OSError as exc:
                self._sock = None
                if time.monotonic() >= deadline:
                    raise BridgeUnavailable(f"{_UNAVAILABLE} ({exc})") from exc
                time.sleep(0.1)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

    def _drain(self, wait: float = 0.0) -> bytes | None:
        """Read whatever the plugin wrote back; None if it hung up."""
        if self._sock is None:
            return None
        data = b""
        try:
            while select.select([self._sock], [], [], wait)[0]:
                chunk = self._sock.recv(4096)
                if not chunk:
                    return None
                data += chunk
                wait = 0.0
        except (OSError, ValueError):
            return None
        return data

    def _send(self, payload: bytes) -> None:
        """Connect and write the request. A failed write leaves no socket; the caller retries."""
        self.connect()
        assert self._sock is not None
        try:
            self._sock.sendall(payload)
        except OSError:
            self.close()

    def call(self, command: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
        """Send one command and wait for its result.

        The plugin serves one connection at a time, so the connection is opened for the call
        and closed straight after. A long-running process (the MCP server) that kept it open
        would lock every other client out.

        Lightroom acknowledges each line it reads with "ok". Right after another client
        disconnects, a new connection can be accepted and then dropped unread while Lightroom
        re-listens; if the connection dies before the acknowledgement, the request is sent
        again. The plugin ignores a reply token it has already seen, so a resend can't run a
        command twice.
        """
        with self._lock:
            request_id = next(self._ids)
            reply = f"{self._session}-{request_id}"
            reply_file = self.response_dir / f"{reply}.json"
            payload = json.dumps(
                {"id": request_id, "command": command, "params": params or {}, "reply": reply}
            ).encode() + b"\n"
            deadline = time.monotonic() + timeout
            acknowledged = False
            try:
                self._send(payload)
                while True:
                    try:
                        text = reply_file.read_text()
                    except FileNotFoundError:
                        text = ""
                    # An empty file has been created but not yet written; keep waiting.
                    if text:
                        reply_file.unlink(missing_ok=True)
                        try:
                            message = json.loads(text)
                        except json.JSONDecodeError as error:
                            raise BridgeError(
                                f"Lightroom sent an unreadable reply to '{command}': {error}"
                            ) from error
                        break
                    if time.monotonic() >= deadline:
                        raise BridgeError(
                            f"Lightroom did not answer '{command}' within {timeout:g}s. It may be busy, "
                            "showing a dialog, or serving another client."
                        )
                    received = self._drain(wait=0.02)
                    if received:
                        acknowledged = True
                    elif received is None:
                        self.close()
                        if acknowledged:
                            # Delivered; the command is running. Only confirm Lightroom is still there.
                            self.connect()
                        else:
                            time.sleep(0.02)
                            self._send(payload)
            finally:
                self.close()
        if not message.get("ok"):
            error = str(message.get("error") or "unknown bridge error")
            # Lua prefixes errors with their source position, e.g. [string "Util.lua"]:46:
            raise BridgeError(re.sub(r'^\[string "[^"]*"\]:\d+: ', "", error))
        return message.get("result")


_shared: Bridge | None = None


def call(command: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
    """Call the bridge over a process-wide connection."""
    global _shared
    if _shared is None:
        _shared = Bridge()
    return _shared.call(command, params, timeout)


def is_available() -> bool:
    try:
        call("ping", timeout=3)
        return True
    except BridgeError:
        return False
