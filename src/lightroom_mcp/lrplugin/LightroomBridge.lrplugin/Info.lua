return {
    LrSdkVersion = 11.0,
    LrSdkMinimumVersion = 6.0,
    LrToolkitIdentifier = "com.lightroommcp.bridge",
    LrPluginName = "Lightroom MCP Bridge",
    LrPluginInfoUrl = "https://github.com/0xB0Bdev/lightroom-mcp",

    LrInitPlugin = "Init.lua",
    LrForceInitPlugin = true,
    LrShutdownPlugin = "Shutdown.lua",
    LrShutdownApp = "ShutdownApp.lua",

    LrLibraryMenuItems = {
        { title = "Bridge Status", file = "StatusMenu.lua" },
    },
    LrExportMenuItems = {
        { title = "Bridge Status", file = "StatusMenu.lua" },
    },

    VERSION = { major = 0, minor = 1, revision = 4 },
}
