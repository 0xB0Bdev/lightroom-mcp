-- Small JSON encoder/decoder for Lua 5.1 (Lightroom's Lua).
-- Tables whose keys are exactly 1..n encode as arrays; empty tables encode as [].
-- Functions, userdata and other non-data values encode as null.

local JSON = {}

local escapes = {
    ['"'] = '\\"', ["\\"] = "\\\\", ["\b"] = "\\b", ["\f"] = "\\f",
    ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t",
}

local function escapeChar(c)
    return escapes[c] or string.format("\\u%04x", string.byte(c))
end

local function isArray(t)
    local n = 0
    for k in pairs(t) do
        if type(k) ~= "number" or k < 1 or k ~= math.floor(k) then
            return false
        end
        if k > n then n = k end
    end
    return n == #t
end

local function encodeValue(v, out, seen)
    local tv = type(v)
    if tv == "nil" then
        out[#out + 1] = "null"
    elseif tv == "boolean" then
        out[#out + 1] = v and "true" or "false"
    elseif tv == "number" then
        if v ~= v or v == math.huge or v == -math.huge then
            out[#out + 1] = "null"
        elseif v == math.floor(v) and math.abs(v) < 1e15 then
            out[#out + 1] = string.format("%d", v)
        else
            out[#out + 1] = string.format("%.14g", v)
        end
    elseif tv == "string" then
        out[#out + 1] = '"' .. string.gsub(v, '[%c"\\]', escapeChar) .. '"'
    elseif tv == "table" then
        if seen[v] then
            out[#out + 1] = "null"
            return
        end
        seen[v] = true
        if isArray(v) then
            out[#out + 1] = "["
            for i = 1, #v do
                if i > 1 then out[#out + 1] = "," end
                encodeValue(v[i], out, seen)
            end
            out[#out + 1] = "]"
        else
            out[#out + 1] = "{"
            local first = true
            for k, val in pairs(v) do
                local tval = type(val)
                if tval ~= "function" and tval ~= "userdata" and tval ~= "thread" then
                    if not first then out[#out + 1] = "," end
                    first = false
                    encodeValue(tostring(k), out, seen)
                    out[#out + 1] = ":"
                    encodeValue(val, out, seen)
                end
            end
            out[#out + 1] = "}"
        end
        seen[v] = nil
    else
        out[#out + 1] = "null"
    end
end

function JSON.encode(value)
    local out = {}
    encodeValue(value, out, {})
    return table.concat(out)
end

-- Decoder -------------------------------------------------------------------

local function utf8(code)
    if code < 0x80 then
        return string.char(code)
    elseif code < 0x800 then
        return string.char(0xC0 + math.floor(code / 0x40), 0x80 + code % 0x40)
    elseif code < 0x10000 then
        return string.char(0xE0 + math.floor(code / 0x1000),
            0x80 + math.floor(code / 0x40) % 0x40, 0x80 + code % 0x40)
    end
    return string.char(0xF0 + math.floor(code / 0x40000),
        0x80 + math.floor(code / 0x1000) % 0x40,
        0x80 + math.floor(code / 0x40) % 0x40, 0x80 + code % 0x40)
end

local unescapes = { b = "\b", f = "\f", n = "\n", r = "\r", t = "\t", ['"'] = '"', ["\\"] = "\\", ["/"] = "/" }

local decodeValue

local function skip(s, i)
    return string.find(s, "[^ \t\r\n]", i) or #s + 1
end

local function decodeString(s, i)
    local parts = {}
    i = i + 1
    while true do
        local j = string.find(s, '["\\]', i)
        if not j then error("JSON: unterminated string") end
        parts[#parts + 1] = string.sub(s, i, j - 1)
        if string.sub(s, j, j) == '"' then
            return table.concat(parts), j + 1
        end
        local c = string.sub(s, j + 1, j + 1)
        if c == "u" then
            local code = tonumber(string.sub(s, j + 2, j + 5), 16)
            if not code then error("JSON: bad unicode escape") end
            i = j + 6
            if code >= 0xD800 and code <= 0xDBFF and string.sub(s, i, i + 1) == "\\u" then
                local low = tonumber(string.sub(s, i + 2, i + 5), 16)
                if low and low >= 0xDC00 and low <= 0xDFFF then
                    code = 0x10000 + (code - 0xD800) * 0x400 + (low - 0xDC00)
                    i = i + 6
                end
            end
            parts[#parts + 1] = utf8(code)
        else
            parts[#parts + 1] = unescapes[c] or c
            i = j + 2
        end
    end
end

decodeValue = function(s, i)
    i = skip(s, i)
    local c = string.sub(s, i, i)
    if c == "{" then
        local obj = {}
        i = skip(s, i + 1)
        if string.sub(s, i, i) == "}" then return obj, i + 1 end
        while true do
            i = skip(s, i)
            if string.sub(s, i, i) ~= '"' then error("JSON: expected string key at " .. i) end
            local key
            key, i = decodeString(s, i)
            i = skip(s, i)
            if string.sub(s, i, i) ~= ":" then error("JSON: expected ':' at " .. i) end
            obj[key], i = decodeValue(s, i + 1)
            i = skip(s, i)
            local d = string.sub(s, i, i)
            if d == "}" then return obj, i + 1 end
            if d ~= "," then error("JSON: expected ',' or '}' at " .. i) end
            i = i + 1
        end
    elseif c == "[" then
        local arr = {}
        i = skip(s, i + 1)
        if string.sub(s, i, i) == "]" then return arr, i + 1 end
        while true do
            arr[#arr + 1], i = decodeValue(s, i)
            i = skip(s, i)
            local d = string.sub(s, i, i)
            if d == "]" then return arr, i + 1 end
            if d ~= "," then error("JSON: expected ',' or ']' at " .. i) end
            i = i + 1
        end
    elseif c == '"' then
        return decodeString(s, i)
    elseif string.sub(s, i, i + 3) == "true" then
        return true, i + 4
    elseif string.sub(s, i, i + 4) == "false" then
        return false, i + 5
    elseif string.sub(s, i, i + 3) == "null" then
        return nil, i + 4
    end
    local num = string.match(s, "^-?%d+%.?%d*[eE]?[-+]?%d*", i)
    if not num or num == "" then error("JSON: unexpected character at " .. i) end
    return tonumber(num), i + #num
end

function JSON.decode(s)
    local value = decodeValue(s, 1)
    return value
end

return JSON
