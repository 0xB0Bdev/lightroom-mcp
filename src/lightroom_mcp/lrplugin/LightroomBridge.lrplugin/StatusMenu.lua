-- Plug-in Extras > Bridge Status
local LrDialogs = import "LrDialogs"

local state = rawget(_G, "LRBRIDGE")
if state and state.running then
    LrDialogs.showBezel(
        "Lightroom MCP Bridge listening on port " .. tostring(state.commandPort))
else
    LrDialogs.message("Lightroom MCP Bridge", "The bridge is not running. Reload the plug-in in Plug-in Manager.", "info")
end
