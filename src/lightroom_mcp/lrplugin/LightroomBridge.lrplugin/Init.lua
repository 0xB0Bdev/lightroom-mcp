-- Runs when Lightroom starts, when the plug-in is reloaded in Plug-in Manager, and when the
-- CLI asks for a full reload ("bridge.restart"). Starts one generation of the bridge server.
--
-- Every other file of the plug-in is loaded through bridge.fresh(), which reads it from disk
-- once per generation and hands it this generation's state as its "..." argument. Lightroom's
-- own require caches files for the life of the application, so it is not used.

local LrTasks = import "LrTasks"
local LrPathUtils = import "LrPathUtils"

-- Ask the server of the previous generation, if any, to stop.
local previous = rawget(_G, "LRBRIDGE")
if previous then
    previous.running = false
end

local bridge = {
    running = true,
    stopped = false,
    generation = (previous and previous.generation or 0) + 1,
}

local cache = {}

function bridge.fresh(name)
    if cache[name] == nil then
        local chunk, err = loadfile(LrPathUtils.child(_PLUGIN.path, name .. ".lua"))
        if not chunk then
            error("could not load " .. name .. ".lua: " .. tostring(err))
        end
        local result = chunk(bridge)
        if result == nil then result = true end
        cache[name] = result
    end
    return cache[name]
end

-- Forget loaded files, so command handlers are read from disk again on their next use.
function bridge.forget()
    cache = {}
end

rawset(_G, "LRBRIDGE", bridge)

LrTasks.startAsyncTask(function()
    if previous then
        -- Give the old server time to release the port before binding it again.
        local waited = 0
        while not previous.stopped and waited < 5 do
            LrTasks.sleep(0.25)
            waited = waited + 0.25
        end
        LrTasks.sleep(0.5)
    end
    if bridge.running then
        bridge.fresh("Server").run(bridge)
    end
    bridge.stopped = true
end)
