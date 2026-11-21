-- Bridge server.
--   Requests:  newline-delimited JSON on a localhost socket   {id, command, params, reply}
--   Responses: one JSON file per request, <responses dir>/<reply>.json   {id, ok, result | error}
--
-- Safety rules for this file (plugin Lua shares Lightroom's main thread, so a blocking call
-- freezes the whole application):
--   * no LrSocket in "send" mode;
--   * never call close() or reconnect() on a socket from outside its own callbacks;
--   * the socket is released only by letting its function context end.
--
-- Responses go through files because LrSocket's "send" mode is not usable for this: it never
-- notices a client disconnecting, and calling reconnect() on it from another task deadlocks
-- Lightroom's main thread (seen on 11.3.1).

local bridge = ...

local LrSocket = import "LrSocket"
local LrTasks = import "LrTasks"
local LrFunctionContext = import "LrFunctionContext"
local LrPathUtils = import "LrPathUtils"
local LrFileUtils = import "LrFileUtils"
local LrPrefs = import "LrPrefs"
local LrLogger = import "LrLogger"

local JSON = bridge.fresh("JSON")
local Dispatch = bridge.fresh("Dispatch")

local log = LrLogger("LightroomBridge")
log:enable("logfile")

local DEFAULT_COMMAND_PORT = 58763

local Server = {}

local function stateDir()
    return LrPathUtils.child(
        LrPathUtils.child(LrPathUtils.child(LrPathUtils.getStandardFilePath("home"), "Library"), "Application Support"),
        "lightroom-mcp")
end

local function writeFile(path, text)
    local file, err = io.open(path, "w")
    if not file then
        error("could not write " .. path .. ": " .. tostring(err))
    end
    file:write(text)
    file:close()
end

-- Write to a temporary name, then rename, so the client never reads a half-written file.
local function writeResponse(dir, reply, text)
    local final = LrPathUtils.child(dir, reply .. ".json")
    local temp = LrPathUtils.child(dir, reply .. ".tmp")
    writeFile(temp, text)
    if not LrFileUtils.move(temp, final) then
        writeFile(final, text)
        LrFileUtils.delete(temp)
    end
end

function Server.run(state)
    local prefs = LrPrefs.prefsForPlugin()
    local commandPort = tonumber(prefs.commandPort) or DEFAULT_COMMAND_PORT
    local responseDir = LrPathUtils.child(stateDir(), "responses")
    state.commandPort = commandPort
    state.responseDir = responseDir

    LrFileUtils.createAllDirectories(responseDir)
    for path in LrFileUtils.files(responseDir) do
        LrFileUtils.delete(path) -- replies nobody collected
    end

    local function respond(reply, response)
        -- The reply name becomes a file name, so accept only plain tokens.
        if type(reply) ~= "string" or not string.match(reply, "^[%w_-]+$") then
            log:warn("request without a usable reply name; dropping the response")
            return
        end
        local ok, encoded = LrTasks.pcall(JSON.encode, response)
        if not ok then
            encoded = JSON.encode({ id = response.id, ok = false, error = "could not encode result: " .. tostring(encoded) })
        end
        local okWrite, err = LrTasks.pcall(writeResponse, responseDir, reply, encoded)
        if not okWrite then
            log:warn("could not write response: " .. tostring(err))
        end
    end

    -- Reply tokens already handled, so a resent request never runs twice. A resend arrives
    -- within moments of the original, so only recent tokens matter: keep two generations and
    -- drop the older one every SEEN_LIMIT requests, which caps memory at 2 * SEEN_LIMIT tokens.
    local SEEN_LIMIT = 500
    local seen, seenBefore, seenCount = {}, {}, 0
    local function alreadySeen(token)
        if seen[token] or seenBefore[token] then return true end
        if seenCount >= SEEN_LIMIT then
            seenBefore, seen, seenCount = seen, {}, 0
        end
        seen[token] = true
        seenCount = seenCount + 1
        return false
    end

    LrFunctionContext.callWithContext("LightroomBridge", function(context)
        -- The socket is closed when this function context ends.
        LrSocket.bind {
            functionContext = context,
            plugin = _PLUGIN,
            port = commandPort,
            mode = "receive",
            onMessage = function(_, message)
                if type(message) ~= "string" or message == "" then return end
                LrTasks.startAsyncTask(function()
                    local okDecode, request = LrTasks.pcall(JSON.decode, message)
                    if not okDecode or type(request) ~= "table" then
                        log:warn("invalid JSON request")
                        return
                    end
                    -- A client resends a request it believes was never delivered; never run one twice.
                    if type(request.reply) == "string" and alreadySeen(request.reply) then
                        return
                    end
                    local ok, result = LrTasks.pcall(Dispatch.handle, state, request.command, request.params or {})
                    if ok then
                        respond(request.reply, { id = request.id, ok = true, result = result })
                    else
                        log:warn(tostring(request.command) .. " failed: " .. tostring(result))
                        respond(request.reply, { id = request.id, ok = false, error = tostring(result) })
                    end
                end)
            end,
            onClosed = function(socket)
                if state.running then socket:reconnect() end
            end,
            onError = function(socket, err)
                if not state.running then return end
                if err ~= "timeout" then
                    log:warn("command socket error: " .. tostring(err))
                end
                socket:reconnect()
            end,
        }

        writeFile(LrPathUtils.child(stateDir(), "bridge.json"),
            JSON.encode({ commandPort = commandPort, responseDir = responseDir }))
        log:info("generation " .. tostring(state.generation) .. " listening on " .. commandPort .. ", responses in " .. responseDir)

        while state.running do
            LrTasks.sleep(0.25)
        end
        log:info("stopping")
    end)
    log:info("stopped, socket closed")
end

return Server
