-- EXALTED Terminal 77
-- Cyberpunk 2077 CET mod: an offline KJV Bible reader (terminal). Pure
-- Lua, no bridge binary: data ships as JSON in <mod>/data and is read
-- with CET's built-in json/io. No network.
--
-- Hotkeys are registered at module load time and can be bound in the CET
-- Overlay under Bindings -> EXALTED (or via bindings.json; 0 = unbound).
--
-- IMPORTANT: registerHotkey must be called at MODULE LOAD TIME (top level),
-- not from app.on_init: CET only *discovers* a mod's hotkeys for the
-- Bindings tab while loading that mod's script file. on_init runs after the
-- overlay has built the Bindings UI, so hotkeys registered there never
-- appear in the Bindings list (though a binding pasted straight into
-- bindings.json would still fire).

local cache = require("lib/cache")
local terminal = require("ui/terminal")

-- CET dispatches draw events ONLY through registerForEvent("onDraw", ...).
-- The returned table is used solely for GetMod() inter-mod communication and
-- its methods are never invoked, so the terminal must be drawn from the
-- registered callback (verified against CET 1.37.1 ScriptContext::TriggerOnDraw).
registerHotkey("OPEN_EXALTED_TERMINAL", "Open EXALTED Terminal", function()
    terminal.toggle()
end)

registerForEvent("onInit", function()
    cache.init()
    -- Release any freeze channel left behind by a mid-game script reload.
    terminal.clearFreeze()
end)

-- CET routes mouse/keyboard into mod ImGui only while the overlay is open
-- (D3D12::SetTrapInputInImGui), so the terminal becomes interactive (cursor,
-- arrow keys, clicks) the moment the overlay opens. Auto-show it there; the
-- hotkey can still put it on screen (read-only) while playing.
registerForEvent("onOverlayOpen", function()
    terminal.onOverlayOpen()
end)

registerForEvent("onOverlayClose", function()
    terminal.onOverlayClose()
end)

registerForEvent("onShutdown", function()
    terminal.clearFreeze()
end)

registerForEvent("onDraw", function()
    cache.poll(os.clock()) -- steps the search-index preloader (books decode)
    if terminal.visible then
        terminal.draw()
    end
end)

return {
    name = "EXALTED",
    version = "0.1.4",
}