"""Launch, quit and restart Lightroom Classic.

This is the only place that uses osascript. The SDK has no relaunch call, and its
quit call (LrApplication.shutdown) only arrived in SDK 14.3, so a clean quit that
works on older versions needs an Apple Event.
"""

from __future__ import annotations

import subprocess
import time
from typing import Any

from .. import bridge, config

PROCESS_NAME = "Adobe Lightroom Classic"


def is_running() -> bool:
    return subprocess.run(["pgrep", "-x", PROCESS_NAME], capture_output=True).returncode == 0


def quit(wait: float = 60.0) -> dict[str, Any]:
    """Ask Lightroom to quit and wait for it to exit."""
    if not is_running():
        return {"running": False, "changed": False}
    result = subprocess.run(
        ["osascript", "-e", f'tell application id "{config.LIGHTROOM_BUNDLE_ID}" to quit'],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not ask Lightroom to quit: {result.stderr.strip()}")
    deadline = time.monotonic() + wait
    while is_running():
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Lightroom is still running after {wait:g}s. It may be showing a dialog "
                "(for example the catalog backup prompt); finish it in Lightroom."
            )
        time.sleep(0.5)
    return {"running": False, "changed": True}


def launch(wait_for_bridge: float = 0.0) -> dict[str, Any]:
    """Start Lightroom. Optionally wait until the bridge plugin answers."""
    already_running = is_running()
    result = subprocess.run(
        ["open", "-b", config.LIGHTROOM_BUNDLE_ID], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not launch Lightroom: {result.stderr.strip()}")
    out: dict[str, Any] = {"running": True, "already_running": already_running}
    if already_running:
        out["note"] = "Lightroom was already running, so nothing was started. If it is frozen, force quit it first."
    if wait_for_bridge > 0:
        deadline = time.monotonic() + wait_for_bridge
        connected = False
        while time.monotonic() < deadline:
            if bridge.is_available():
                connected = True
                break
            time.sleep(1)
        out["bridge_connected"] = connected
    return out


def restart(wait_for_bridge: float = 60.0) -> dict[str, Any]:
    """Quit and relaunch Lightroom (needed for plugin installs and removals to take effect)."""
    quit()
    time.sleep(1)
    return launch(wait_for_bridge)
