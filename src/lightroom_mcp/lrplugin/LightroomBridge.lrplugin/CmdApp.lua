local bridge = ...

local LrApplication = import "LrApplication"
local LrApplicationView = import "LrApplicationView"

local Util = bridge.fresh("Util")

local handlers = {}

handlers["ping"] = function()
    return { pong = true }
end

handlers["status"] = function(_, state)
    local catalog = Util.catalog()
    local active = catalog:getTargetPhoto()
    return {
        lightroom_version = LrApplication.versionString(),
        catalog = catalog:getPath(),
        module = LrApplicationView.getCurrentModuleName(),
        selected_count = active and #catalog:getTargetPhotos() or 0,
        command_port = state.commandPort,
        response_dir = state.responseDir,
        generation = state.generation,
    }
end

return handlers
