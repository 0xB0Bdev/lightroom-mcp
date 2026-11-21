local bridge = ...

local LrApplication = import "LrApplication"
local LrApplicationView = import "LrApplicationView"
local LrDevelopController = import "LrDevelopController"
local LrTasks = import "LrTasks"

local Util = bridge.fresh("Util")

local handlers = {}

local function pick(settings, keys)
    if not keys or #keys == 0 then
        return settings
    end
    local out = {}
    for _, key in ipairs(keys) do
        out[key] = settings[key]
    end
    return out
end

handlers["develop.get"] = function(params)
    local out = {}
    for i, photo in ipairs(Util.photos(params)) do
        out[i] = {
            id = photo.localIdentifier,
            filename = photo:getFormattedMetadata("fileName"),
            settings = pick(photo:getDevelopSettings(), params.keys),
        }
    end
    return out
end

handlers["develop.set"] = function(params)
    local settings = params.settings or {}
    return Util.writeEach("Apply Develop Settings", params, function(photo)
        photo:applyDevelopSettings(settings)
    end)
end

handlers["develop.copy"] = function(params)
    local source = Util.photos({ ids = { params.source }, uuids = params.sourceUuids })[1]
    local settings = pick(source:getDevelopSettings(), params.keys)
    local result = Util.writeEach("Paste Develop Settings", params, function(photo)
        photo:applyDevelopSettings(settings)
    end)
    result.source = source.localIdentifier
    return result
end

handlers["develop.presets"] = function()
    local out = {}
    for _, folder in ipairs(LrApplication.developPresetFolders()) do
        local presets = {}
        for _, preset in ipairs(folder:getDevelopPresets()) do
            presets[#presets + 1] = { name = preset:getName(), uuid = preset:getUuid() }
        end
        out[#out + 1] = { folder = folder:getName(), presets = presets }
    end
    return out
end

local function findPreset(wanted)
    local byUuid = LrApplication.developPresetByUuid(wanted)
    if byUuid then return byUuid end
    local lower = string.lower(wanted)
    local found = {}
    for _, folder in ipairs(LrApplication.developPresetFolders()) do
        for _, preset in ipairs(folder:getDevelopPresets()) do
            if string.lower(preset:getName()) == lower then
                found[#found + 1] = preset
            end
        end
    end
    if #found == 0 then
        error("No develop preset named '" .. wanted .. "'.")
    elseif #found > 1 then
        error("Several develop presets are named '" .. wanted .. "'; use the preset's uuid.")
    end
    return found[1]
end

handlers["develop.applyPreset"] = function(params)
    local preset = findPreset(tostring(params.preset))
    local result = Util.writeEach("Apply Develop Preset", params, function(photo)
        photo:applyDevelopPreset(preset, _PLUGIN)
    end)
    result.preset = preset:getName()
    return result
end

handlers["develop.virtualCopy"] = function(params)
    local catalog = Util.catalog()
    local photos = Util.photos(params)
    catalog:setSelectedPhotos(photos[1], photos)
    local copyName = params.copyName
    -- Called outside a write gate, as the SDK documents; it opens its own.
    local copies = catalog:createVirtualCopies(copyName)
    local out = {}
    for i, copy in ipairs(copies or {}) do
        out[i] = Util.summary(copy)
    end
    return { created = #out, copies = out }
end

handlers["develop.reset"] = function(params)
    local catalog = Util.catalog()
    local photos = Util.photos(params)
    -- The SDK only resets the active photo, and only in the Develop module.
    -- That changes the module and the selection, so put both back afterwards.
    local previousModule = LrApplicationView.getCurrentModuleName()
    local previousActive = catalog:getTargetPhoto()
    local previousSelection = previousActive and catalog:getTargetPhotos() or nil
    if previousModule ~= "develop" then
        LrApplicationView.switchToModule("develop")
        LrTasks.sleep(1)
    end
    for _, photo in ipairs(photos) do
        catalog:setSelectedPhotos(photo, { photo })
        LrTasks.sleep(0.5)
        LrDevelopController.resetAllDevelopAdjustments()
        LrTasks.sleep(0.3)
    end
    if previousActive then
        catalog:setSelectedPhotos(previousActive, previousSelection)
    end
    if previousModule and previousModule ~= "develop" then
        LrApplicationView.switchToModule(previousModule)
    end
    return { updated = #photos, ids = Util.ids(photos) }
end

return handlers
