-- Runs when the plugin is disabled or reloaded: stop the socket server.
local state = rawget(_G, "LRBRIDGE")
if state then
    state.running = false
end
