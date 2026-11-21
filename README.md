# lightroom-mcp

Control Adobe Lightroom Classic from the command line, and expose the same operations to AI agents through an MCP server.

- **Search and inspect** photos, collections and keywords (reads the catalog directly; Lightroom can be closed)
- **Organize**: ratings, flags, color labels, keywords, text metadata, collections
- **Develop**: read and apply settings, presets, copy settings, virtual copies
- **Export** through Lightroom's own renderer
- **Plugins**: list, install, uninstall, reload; restart Lightroom

macOS only. Built against Lightroom Classic 11 (SDK 11).

## How it works

```
lightroom-mcp (Typer) ─┐
                       ├─> core functions ─┬─> catalog.py   read-only SQLite on the .lrcat
lightroom-mcp mcp ─────┘                   ├─> bridge.py    JSON lines over a localhost socket, replies as files
(FastMCP, stdio)                           └─> plugins/app  files in Modules/, osascript to quit
                                                  │
                              LightroomBridge.lrplugin (Lua, runs inside Lightroom)
```

Reads go straight to the catalog file, opened read-only. Anything that changes Lightroom goes through a small Lua plugin that runs inside Lightroom and uses the official SDK, so every change is a normal undoable Lightroom action. The catalog file is never written to directly.

## Setup

Install the `lightroom-mcp` command:

```bash
uv tool install lightroom-mcp
```

(or `pipx install lightroom-mcp`). Then install the bridge plugin:

```bash
lightroom-mcp plugins bridge-install --restart
```

This copies the plugin into `~/Library/Application Support/Adobe/Lightroom/Modules/` and restarts Lightroom so it loads. Check it with:

```bash
lightroom-mcp status
```

After upgrading lightroom-mcp, run `bridge-install` again so the plugin matches.

## Usage

Photos are addressed by catalog id (the `id` column from `photos search`) or with `--selected` for the current Lightroom selection. Add `--json` before the command for machine-readable output.

```bash
lightroom-mcp photos search --rating ">=3" --camera "EOS" --after 2026-01-01
lightroom-mcp photos show 153 --develop
lightroom-mcp photos selected

lightroom-mcp organize rate 4 153 194
lightroom-mcp organize flag picked --selected
lightroom-mcp organize label red 153
lightroom-mcp organize set-metadata 153 -f title="Studio test" -f caption="First roll"
lightroom-mcp keywords add "film,studio" 153 194
lightroom-mcp collections create "Best Of"
lightroom-mcp collections add "Best Of" 153 194

lightroom-mcp develop get 153 --keys Exposure2012,Temperature,Tint
lightroom-mcp develop set Exposure2012=0.5 Contrast2012=10 --id 153
lightroom-mcp develop copy 153 194 229 --keys Temperature,Tint
lightroom-mcp develop presets
lightroom-mcp develop apply-preset "My Preset" --selected
lightroom-mcp develop virtual-copy 153

lightroom-mcp export 153 194 --to ~/Desktop/out --format jpeg --quality 85 --long-edge 2048

lightroom-mcp plugins list
lightroom-mcp plugins install ~/dev/MyPlugin.lrplugin --link --restart
lightroom-mcp plugins uninstall MyPlugin --restart
lightroom-mcp plugins reload
lightroom-mcp plugins extras
lightroom-mcp app restart
```

## MCP server

`lightroom-mcp mcp` runs a FastMCP server over stdio. To add it to Claude Code:

```bash
claude mcp add lightroom -- uvx lightroom-mcp mcp
```

Or in a JSON MCP config (Claude Desktop and others):

```json
{
  "mcpServers": {
    "lightroom": {
      "command": "uvx",
      "args": ["lightroom-mcp", "mcp"]
    }
  }
}
```

Tools mirror the CLI: `search_photos`, `get_photo`, `selected_photos`, `set_rating`, `set_flag`, `set_color_label`, `add_keywords`, `set_metadata`, `create_collection`, `add_to_collection`, `get_develop_settings`, `apply_develop_settings`, `apply_develop_preset`, `copy_develop_settings`, `create_virtual_copies`, `export_photos`, `list_plugins`, `install_plugin`, `uninstall_plugin`, `reload_plugin`, `restart_lightroom` and more. Read-only tools are annotated as such; tools that overwrite edits, delete plugins or restart Lightroom are marked destructive.

## Plugin management limits

The Lightroom SDK has no API for installing, removing or reloading plugins, or for one plugin to run another's menu commands. So:

- `install` / `uninstall` copy into or delete from Lightroom's user `Modules` folder and take effect on restart. Plugins added through Plug-in Manager are listed but must be removed there.
- `reload` restarts the bridge plugin in place (its server and command handlers) without restarting Lightroom. Any other plugin is reloaded by restarting Lightroom (`--restart`).
- `plugins extras` lists every plugin's Plug-in Extras commands; `run-extra` can only run the bridge's own.
- `osascript` is used only to ask Lightroom to quit. No UI scripting, no Accessibility permission.

## Configuration

| Variable | Purpose |
|---|---|
| `LIGHTROOM_CATALOG` | Path to the `.lrcat` to read. Default: `~/Pictures/Lightroom/Lightroom Catalog.lrcat` |
| `LIGHTROOM_BRIDGE_PORT` | Port the bridge plugin listens on. Default: 58763 |

## Security

The bridge listens on localhost only and has no authentication: any local process can send it commands while Lightroom is open. Don't install it on a shared machine.

## Development

```bash
git clone https://github.com/0xB0Bdev/lightroom-mcp.git
cd lightroom-mcp
uv sync
uv run pytest
```

Run the CLI from the checkout with `uv run lightroom-mcp …`. Install the bridge with `--link` to work on the Lua handlers in place; `lightroom-mcp plugins reload` picks up edits to any of the plugin's Lua files without restarting Lightroom.

## License

[MIT](https://github.com/0xB0Bdev/lightroom-mcp/blob/main/LICENSE)
