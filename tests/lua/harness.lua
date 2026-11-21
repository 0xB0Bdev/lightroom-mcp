-- Runs the bridge plug-in's Lua outside Lightroom against stand-ins for the SDK.
-- usage: luajit harness.lua <plugin dir> <home dir>
local pluginDir, home = arg[1], arg[2]

local tasks = {}
local sockets = {}
local warnings = {}

local sdk = {}
sdk.LrTasks = {
    startAsyncTask = function(fn) tasks[#tasks + 1] = coroutine.create(fn) end,
    sleep = function() coroutine.yield() end,
    yield = function() coroutine.yield() end,
    pcall = pcall,
}
sdk.LrFunctionContext = { callWithContext = function(_, fn) return fn({}) end }
sdk.LrPathUtils = {
    child = function(a, b) return a .. "/" .. b end,
    getStandardFilePath = function() return home end,
}
sdk.LrFileUtils = {
    createAllDirectories = function(dir) os.execute('mkdir -p "' .. dir .. '"') end,
    files = function() return function() return nil end end,
    move = function(a, b) return os.rename(a, b) end,
    delete = function(path) os.remove(path) end,
}
sdk.LrPrefs = { prefsForPlugin = function() return {} end }
sdk.LrLogger = function()
    return {
        enable = function() end,
        info = function() end,
        warn = function(_, message) warnings[#warnings + 1] = message end,
    }
end
sdk.LrSocket = {
    bind = function(options)
        sockets[#sockets + 1] = options
        return {}
    end,
}

function import(name)
    return sdk[name] or {}
end
_PLUGIN = { path = pluginDir }

local function step(times)
    for _ = 1, times or 1 do
        for i = #tasks, 1, -1 do
            local task = tasks[i]
            local ok, err = coroutine.resume(task)
            if not ok then error("task failed: " .. tostring(err)) end
            if coroutine.status(task) == "dead" then table.remove(tasks, i) end
        end
    end
end

local responses = home .. "/Library/Application Support/lightroom-mcp/responses/"
local function reply(token)
    local file = io.open(responses .. token .. ".json")
    if not file then return nil end
    local text = file:read("*a")
    file:close()
    os.remove(responses .. token .. ".json")
    return text
end
local function send(command, token)
    sockets[#sockets].onMessage(nil, '{"id":1,"command":"' .. command .. '","params":{},"reply":"' .. token .. '"}')
    step(3)
    return reply(token)
end
local function check(condition, message)
    if not condition then error("FAILED: " .. message, 2) end
end

dofile(pluginDir .. "/Init.lua")
step(3)
check(#sockets == 1 and sockets[1].mode == "receive", "generation 1 binds one receive socket")
local first = rawget(_G, "LRBRIDGE")
check(first.generation == 1, "first generation is 1")

local pong = send("ping", "t1")
check(pong and pong:find('"pong":true'), "ping is answered: " .. tostring(pong))
check(send("ping", "t1") == nil, "a repeated reply token is not run again")
check(send("ping", "../evil") == nil, "an unsafe reply name is refused")
local unknown = send("nope.nope", "t2")
check(unknown and unknown:find('"ok":false'), "an unknown command returns an error")
check(send("bridge.reload", "t3"):find('"reloaded":true'), "handler reload works")
check(send("ping", "t4"):find('"pong":true'), "ping still works after a handler reload")

local restarting = send("bridge.restart", "t5")
check(restarting and restarting:find('"restarting":true'), "restart is acknowledged: " .. tostring(restarting))
step(40)
local second = rawget(_G, "LRBRIDGE")
check(second ~= first and second.generation == 2, "restart starts generation 2")
check(first.running == false and first.stopped == true, "generation 1 has stopped")
check(#sockets == 2, "generation 2 binds a new socket")
check(send("ping", "t6"):find('"pong":true'), "generation 2 answers")
check(send("ping", "t1"):find('"pong":true'), "generation 2 starts with a clean token table")

-- Lightroom's shutdown hooks stop the running generation.
dofile(pluginDir .. "/Shutdown.lua")
step(5)
check(second.running == false and second.stopped == true, "shutdown stops the server")
check(#tasks == 0, "no tasks left running")
print("OK")
