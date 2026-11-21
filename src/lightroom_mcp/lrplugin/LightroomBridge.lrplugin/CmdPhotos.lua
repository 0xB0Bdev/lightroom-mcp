local bridge = ...

local Util = bridge.fresh("Util")

local handlers = {}

handlers["photos.selected"] = function()
    local catalog = Util.catalog()
    local out = {}
    if catalog:getTargetPhoto() then
        for i, photo in ipairs(catalog:getTargetPhotos()) do
            out[i] = Util.summary(photo)
        end
    end
    return out
end

handlers["photos.select"] = function(params)
    local photos = Util.photos(params)
    Util.catalog():setSelectedPhotos(photos[1], photos)
    return { selected = #photos, ids = Util.ids(photos) }
end

return handlers
