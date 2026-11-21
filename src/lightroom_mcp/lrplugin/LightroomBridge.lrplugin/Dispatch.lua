-- Routes a command name such as "organize.rate" to its handler file.
--   bridge.reload   re-reads the command handlers (Cmd*.lua, Util.lua) on their next use
--   bridge.restart  starts a new generation of the whole plug-in: server, dispatch, handlers

local bridge = ...

local LrPathUtils = import "LrPathUtils"
local LrTasks = import "LrTasks"
local LrLogger = import "LrLogger"

local log = LrLogger("LightroomBridge")
log:enable("logfile")

local Dispatch = {}

local MODULES = {
    ping = "CmdApp",
    status = "CmdApp",
    photos = "CmdPhotos",
    organize = "CmdOrganize",
    collections = "CmdOrganize",
    develop = "CmdDevelop",
    export = "CmdExport",
}

local EXTRAS = {
    ["Bridge Status"] = "StatusMenu.lua",
}

function Dispatch.handle(state, command, params)
    if type(command) ~= "string" then
        error("missing command")
    end

    if command == "bridge.reload" then
        bridge.forget()
        bridge.fresh("CmdApp") -- load one file now so a syntax error is reported immediately
        return { reloaded = true, generation = bridge.generation }
    elseif command == "bridge.restart" then
        local chunk, err = loadfile(LrPathUtils.child(_PLUGIN.path, "Init.lua"))
        if not chunk then
            error("could not load Init.lua: " .. tostring(err))
        end
        LrTasks.startAsyncTask(function()
            -- Let this reply be written and the client hang up first, so the server socket is
            -- released with nobody connected.
            LrTasks.sleep(1)
            log:info("restart requested; ending generation " .. tostring(bridge.generation))
            chunk()
        end)
        return { restarting = true, generation = bridge.generation }
    elseif command == "bridge.runExtra" then
        local file = EXTRAS[params.title or ""]
        if not file then
            error("the bridge has no Plug-in Extras command titled '" .. tostring(params.title) .. "'")
        end
        LrTasks.startAsyncTask(function()
            dofile(LrPathUtils.child(_PLUGIN.path, file))
        end)
        return { started = params.title }
    end

    local prefix = string.match(command, "^([^.]+)")
    local name = MODULES[prefix]
    if not name then
        error("unknown command '" .. command .. "'")
    end
    local handler = bridge.fresh(name)[command]
    if not handler then
        error("unknown command '" .. command .. "'")
    end
    return handler(params, state)
end

return Dispatch
