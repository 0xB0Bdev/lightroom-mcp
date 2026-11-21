"""Set the bridge plugin's VERSION in Info.lua to the package version in pyproject.toml.

Run by semantic-release's build_command after it bumps pyproject.toml, so the plugin
Lightroom shows always matches the released package.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INFO_LUA = ROOT / "src/lightroom_mcp/lrplugin/LightroomBridge.lrplugin/Info.lua"
VERSION_TABLE = re.compile(r"VERSION\s*=\s*\{[^}]*\}")


def main() -> int:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        print(f"Unexpected version {version!r} in pyproject.toml", file=sys.stderr)
        return 1
    major, minor, revision = match.groups()
    text = INFO_LUA.read_text()
    updated, count = VERSION_TABLE.subn(
        f"VERSION = {{ major = {major}, minor = {minor}, revision = {revision} }}", text
    )
    if count != 1:
        print(f"Expected one VERSION table in {INFO_LUA}, found {count}", file=sys.stderr)
        return 1
    INFO_LUA.write_text(updated)
    print(f"Info.lua VERSION set to {major}.{minor}.{revision}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
