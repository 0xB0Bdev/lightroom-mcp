local bridge = ...

local Util = bridge.fresh("Util")

local handlers = {}

handlers["organize.rate"] = function(params)
    local rating = tonumber(params.rating) or 0
    return Util.writeEach("Set Rating", params, function(photo)
        if rating > 0 then
            photo:setRawMetadata("rating", rating)
        else
            photo:setRawMetadata("rating", nil)
        end
    end)
end

handlers["organize.flag"] = function(params)
    local pick = tonumber(params.pick) or 0
    return Util.writeEach("Set Flag", params, function(photo)
        photo:setRawMetadata("pickStatus", pick)
    end)
end

handlers["organize.label"] = function(params)
    local label = params.label or "none"
    return Util.writeEach("Set Color Label", params, function(photo)
        photo:setRawMetadata("colorNameForLabel", label)
    end)
end

handlers["organize.setMetadata"] = function(params)
    return Util.writeEach("Set Metadata", params, function(photo)
        for field, value in pairs(params.fields or {}) do
            photo:setRawMetadata(field, value)
        end
    end)
end

handlers["organize.addKeywords"] = function(params)
    local catalog = Util.catalog()
    local photos = Util.photos(params)
    local keywords = {}
    -- Keywords created in a write gate can only be used after it completes, so use two steps.
    Util.write("Create Keywords", function()
        for i, name in ipairs(params.keywords or {}) do
            keywords[i] = catalog:createKeyword(name, {}, true, nil, true)
        end
    end)
    Util.write("Add Keywords", function()
        for _, photo in ipairs(photos) do
            for _, keyword in ipairs(keywords) do
                photo:addKeyword(keyword)
            end
        end
    end)
    return { updated = #photos, ids = Util.ids(photos), keywords = params.keywords }
end

handlers["organize.removeKeywords"] = function(params)
    local wanted = {}
    for _, name in ipairs(params.keywords or {}) do
        wanted[string.lower(name)] = true
    end
    local removed = 0
    local result = Util.writeEach("Remove Keywords", params, function(photo)
        for _, keyword in ipairs(photo:getRawMetadata("keywords") or {}) do
            if wanted[string.lower(keyword:getName())] then
                photo:removeKeyword(keyword)
                removed = removed + 1
            end
        end
    end)
    result.removed = removed
    return result
end

-- Collections ---------------------------------------------------------------

local function matches(item, wanted)
    return tostring(item.localIdentifier) == wanted or string.lower(item:getName()) == string.lower(wanted)
end

local function findIn(parent, wanted, wantSet)
    if not wantSet then
        for _, collection in ipairs(parent:getChildCollections()) do
            if matches(collection, wanted) then return collection end
        end
    end
    for _, set in ipairs(parent:getChildCollectionSets()) do
        if wantSet and matches(set, wanted) then return set end
        local found = findIn(set, wanted, wantSet)
        if found then return found end
    end
    return nil
end

local function findCollection(wanted)
    local collection = findIn(Util.catalog(), tostring(wanted), false)
    if not collection then
        error("No collection named or with id '" .. tostring(wanted) .. "'.")
    end
    if collection:isSmartCollection() then
        error("'" .. collection:getName() .. "' is a smart collection; its photos are chosen by its rules.")
    end
    return collection
end

handlers["collections.create"] = function(params)
    local catalog = Util.catalog()
    local parent = nil
    if params.parent and params.parent ~= "" then
        parent = findIn(catalog, tostring(params.parent), true)
        if not parent then
            error("No collection set named or with id '" .. tostring(params.parent) .. "'.")
        end
    end
    local collection
    Util.write("Create Collection", function()
        collection = catalog:createCollection(params.name, parent, true)
    end)
    if not collection then
        error("Lightroom did not create the collection.")
    end
    return { id = collection.localIdentifier, name = collection:getName() }
end

handlers["collections.add"] = function(params)
    local collection = findCollection(params.collection)
    local photos = Util.photos(params)
    Util.write("Add to Collection", function()
        collection:addPhotos(photos)
    end)
    return { collection = collection:getName(), added = #photos, ids = Util.ids(photos) }
end

handlers["collections.remove"] = function(params)
    local collection = findCollection(params.collection)
    local photos = Util.photos(params)
    Util.write("Remove from Collection", function()
        collection:removePhotos(photos)
    end)
    return { collection = collection:getName(), removed = #photos, ids = Util.ids(photos) }
end

return handlers
