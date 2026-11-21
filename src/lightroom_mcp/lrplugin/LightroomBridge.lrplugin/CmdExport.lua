local bridge = ...

local LrExportSession = import "LrExportSession"

local Util = bridge.fresh("Util")

local handlers = {}

handlers["export.run"] = function(params)
    local photos = Util.photos(params)
    local settings = {
        LR_export_destinationType = "specificFolder",
        LR_export_destinationPathPrefix = params.destination,
        LR_export_useSubfolder = false,
        LR_format = params.format or "JPEG",
        LR_jpeg_quality = tonumber(params.quality) or 0.9,
        LR_export_colorSpace = params.colorSpace or "sRGB",
        LR_export_bitDepth = 8,
        LR_tiff_compressionMethod = "compressionMethod_ZIP",
        LR_collisionHandling = params.collision or "rename",
        LR_reimportExportedPhoto = false,
        LR_renamingTokensOn = false,
        LR_includeVideoFiles = true,
        LR_minimizeEmbeddedMetadata = false,
        LR_removeLocationMetadata = false,
        LR_outputSharpeningOn = false,
        LR_useWatermark = false,
        LR_size_doConstrain = false,
        LR_export_postProcessing = "doNothing",
    }
    local longEdge = tonumber(params.longEdge)
    if longEdge and longEdge > 0 then
        settings.LR_size_doConstrain = true
        settings.LR_size_resizeType = "longEdge"
        settings.LR_size_maxWidth = longEdge
        settings.LR_size_maxHeight = longEdge
        settings.LR_size_units = "pixels"
        settings.LR_size_doNotEnlarge = true
        settings.LR_size_resolution = 240
        settings.LR_size_resolutionUnits = "inch"
    end

    local session = LrExportSession({ photosToExport = photos, exportSettings = settings })
    session:doExportOnCurrentTask()

    local files, errors = {}, {}
    for _, rendition in session:renditions() do
        local ok, pathOrMessage = rendition:waitForRender()
        if ok then
            files[#files + 1] = { id = rendition.photo.localIdentifier, path = pathOrMessage }
        else
            errors[#errors + 1] = { id = rendition.photo.localIdentifier, error = tostring(pathOrMessage) }
        end
    end
    return {
        destination = params.destination,
        exported = #files,
        failed = #errors,
        files = files,
        errors = errors,
    }
end

return handlers
