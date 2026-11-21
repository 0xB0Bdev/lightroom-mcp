-- Runs when Lightroom quits: stop the socket server so shutdown isn't held up.
return {
    LrShutdownFunction = function(doneFunction, progressFunction)
        local state = rawget(_G, "LRBRIDGE")
        if state then
            state.running = false
        end
        doneFunction()
    end,
}
