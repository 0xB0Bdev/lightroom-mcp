-- Helpers shared by the command handlers.

local LrApplication = import "LrApplication"
local LrTasks = import "LrTasks"

local Util = {}

function Util.catalog()
    return LrApplication.activeCatalog()
end

-- The SDK has no lookup by local id, so: try the UUID the client sent, else scan the catalog once.
local function resolver(catalog, uuids)
    local byId = nil
    return function(id)
        local uuid = uuids and uuids[tostring(id)]
        if uuid then
            local photo = catalog:findPhotoByUuid(uuid)
            if photo and photo.localIdentifier == id then
                return photo
            end
        end
        if not byId then
            byId = {}
            for i, photo in ipairs(catalog:getAllPhotos()) do
                byId[photo.localIdentifier] = photo
                -- Plugin code shares Lightroom's main thread; give it back regularly on big catalogs.
                if i % 500 == 0 then LrTasks.yield() end
            end
        end
        return byId[id]
    end
end

-- Photos named by params: { ids = {..}, uuids = { [id] = uuid } } or { selected = true }.
function Util.photos(params)
    local catalog = Util.catalog()
    if params.selected then
        if not catalog:getTargetPhoto() then
            error("No photos are selected in Lightroom.")
        end
        return catalog:getTargetPhotos()
    end
    local find = resolver(catalog, params.uuids)
    local photos = {}
    for _, id in ipairs(params.ids or {}) do
        local photo = find(tonumber(id))
        if not photo then
            error("No photo with id " .. tostring(id) .. " in the open catalog.")
        end
        photos[#photos + 1] = photo
    end
    if #photos == 0 then
        error("No photos given.")
    end
    return photos
end

local FLAGS = { [1] = "picked", [0] = "unflagged", [-1] = "rejected" }

function Util.summary(photo)
    -- Lightroom reports "grey" for a photo with no color label.
    local label = photo:getRawMetadata("colorNameForLabel") or ""
    if label == "grey" or label == "none" then label = "" end
    return {
        id = photo.localIdentifier,
        filename = photo:getFormattedMetadata("fileName"),
        path = photo:getRawMetadata("path"),
        rating = photo:getRawMetadata("rating") or 0,
        flag = FLAGS[photo:getRawMetadata("pickStatus") or 0] or "unflagged",
        label = label,
        virtual_copy = photo:getRawMetadata("isVirtualCopy") or false,
    }
end

function Util.ids(photos)
    local ids = {}
    for i, photo in ipairs(photos) do
        ids[i] = photo.localIdentifier
    end
    return ids
end

-- Run fn inside a catalog write gate as one named undo step.
function Util.write(actionName, fn)
    local result = Util.catalog():withWriteAccessDo(actionName, fn, { timeout = 15 })
    if result == "aborted" then
        error("Lightroom's catalog is busy (another operation holds write access). Try again.")
    end
end

-- Apply fn(photo) to each photo in one undo step; returns { updated = n, ids = {...} }.
function Util.writeEach(actionName, params, fn)
    local photos = Util.photos(params)
    Util.write(actionName, function()
        for _, photo in ipairs(photos) do
            fn(photo)
        end
    end)
    return { updated = #photos, ids = Util.ids(photos) }
end

return Util
