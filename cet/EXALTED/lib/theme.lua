-- EXALTED Terminal 77: dark palette matching the out-of-game TUI
-- (cmd/biblelearn/tui_theme.go). Uses only ImGui primitives proven in
-- installed CET mods (PushStyleColor/PopStyleColor, SetWindowFontScale,
-- BeginChild, etc.).

local theme = {}

-- Palette (0xFFRRGGBB ints, the ImGui color format used by nativeInteractions).
-- Mirrors the TUI dark scheme: low-glare background with an amber accent.
theme.bg        = 0xFF0d1117 -- tBg   background
theme.panel     = 0xFF0d1117 -- tBg   flat panels (TUI style)
theme.border    = 0xFF30363d -- tBorder
theme.green     = 0xFFf5a623 -- tAccent (amber accent / highlights)
theme.greenDim  = 0xFF8b949e -- tMuted
theme.greenMid  = 0xFF1f6feb -- tSel   (selection blue)
theme.greenFaint= 0xFF484f58 -- tDim
theme.amber     = 0xFFf5a623 -- tAccent warning / status
theme.red       = 0xFFf85149 -- tWarn errors
theme.white     = 0xFFffd479 -- tAccentHi bright headers
theme.base      = 0xFFe6edf3 -- tFg main text
function theme.palette_crt()
    theme.green = 0xFFf5a623
    theme.greenDim  = 0xFF8b949e
    theme.greenMid  = 0xFF1f6feb
    theme.greenFaint= 0xFF484f58
    theme.border    = 0xFF30363d
end

-- Glass translucency (0..1, 1 = opaque). Container surfaces (window, child
-- panels) render see-through by this amount so the game shows behind the
-- terminal; text and highlights stay fully opaque. The terminal draws the
-- game behind a dark pane; the About tab exposes a +/- control that writes a
-- persisted glass value in cache settings.
theme.glass = 0.45
theme._depth = 0

-- Set the alpha (top) byte of a 0xFFRRGGBB color. Arithmetic-only so it stays
-- safe on CET's Lua VM. ImGui's packed U32 treats the top byte as alpha, so a
-- color like 0xFF0d1117 -> glass 0.55 -> 0x8C0d1117 (~55% opaque).
function theme.withAlpha(color, alpha)
    local a = math.floor((alpha or theme.glass) * 255)
    local rgb = color % 16777216 -- strip the alpha byte
    return rgb + a * 16777216
end

function theme.text(text, color, scale)
    if not text or text == "" then return end
    if color then ImGui.PushStyleColor(ImGuiCol.Text, color) end
    if scale then ImGui.SetWindowFontScale(scale) end
    ImGui.Text(text)
    if scale then ImGui.SetWindowFontScale(1) end
    if color then ImGui.PopStyleColor() end
end

function theme.textWrapped(text, color, scale)
    if not text or text == "" then return end
    if color then ImGui.PushStyleColor(ImGuiCol.Text, color) end
    if scale then ImGui.SetWindowFontScale(scale) end
    ImGui.TextWrapped(text)
    if scale then ImGui.SetWindowFontScale(1) end
    if color then ImGui.PopStyleColor() end
end

function theme.bright(text, scale)
    theme.text(text, theme.white, scale or 1.0)
end

function theme.dim(text)
    theme.text(text, theme.greenDim, 0.9)
end

function theme.faint(text)
    theme.text(text, theme.greenFaint, 0.8)
end

function theme.sep()
    ImGui.PushStyleColor(ImGuiCol.Separator, theme.border)
    ImGui.Spacing()
    ImGui.Separator()
    ImGui.Spacing()
    ImGui.PopStyleColor()
end

function theme.panelBegin(name, w, h)
    theme._depth = theme._depth + 1
    local a = math.min(1, theme.glass + theme._depth * 0.06) -- nested panels stack slightly
    ImGui.PushStyleColor(ImGuiCol.ChildBg, theme.withAlpha(theme.panel, a))
    ImGui.PushStyleColor(ImGuiCol.Border, theme.border)
    return ImGui.BeginChild(name, w, h, true)
end

function theme.panelEnd()
    ImGui.PopStyleColor(2)
    ImGui.EndChild()
    if theme._depth > 0 then theme._depth = theme._depth - 1 end
end

-- Mouse-only click detection. Button()/Selectable() return true on mouse
-- RELEASE (and on keyboard Enter/Space when focused), while
-- IsItemClicked() is true on mouse PRESS. Returning IsItemClicked() keeps
-- every widget mouse-only: keyboard can never fire a button, and the click
-- registers on press. Must be called immediately after the widget.
local function mouseClicked()
    return ImGui.IsItemClicked(ImGuiMouseButton.Left)
end

-- EXALTED runs its OWN keyboard navigation, and only for the books rail and
-- reading panel. ImGui's built-in keyboard/gamepad nav must be silenced on our
-- clickable widgets, otherwise arrow keys independently move ImGui's nav
-- highlight (and can activate) the top tab bar and the lists. Existence-guarded
-- so a missing binding can never break the mod.
local ITEM_NO_NAV = nil
if ImGuiItemFlags then
    ITEM_NO_NAV = ImGuiItemFlags.NoNav or ImGuiItemFlags.NoNavInputs or ImGuiItemFlags.NoNavFocus
end

local function navPush()
    if ITEM_NO_NAV ~= nil and type(ImGui.PushItemFlag) == "function" then
        ImGui.PushItemFlag(ITEM_NO_NAV, true)
        return "item"
    end
    if type(ImGui.PushAllowKeyboardFocus) == "function" then
        ImGui.PushAllowKeyboardFocus(false)
        return "focus"
    end
    return nil
end

local function navPop(tag)
    if tag == "item" and type(ImGui.PopItemFlag) == "function" then
        ImGui.PopItemFlag()
    elseif tag == "focus" and type(ImGui.PopAllowKeyboardFocus) == "function" then
        ImGui.PopAllowKeyboardFocus()
    end
end

function theme.button(label)
    ImGui.PushStyleColor(ImGuiCol.Button, theme.panel)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, theme.greenMid)
    ImGui.PushStyleColor(ImGuiCol.ButtonActive, theme.border)
    ImGui.PushStyleColor(ImGuiCol.Text, theme.green)
    local nav = navPush()
    ImGui.Button(label)
    local clicked = mouseClicked()
    navPop(nav)
    ImGui.PopStyleColor(4)
    return clicked
end

function theme.buttonDim(label)
    ImGui.PushStyleColor(ImGuiCol.Button, theme.panel)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, theme.border)
    ImGui.PushStyleColor(ImGuiCol.ButtonActive, theme.border)
    ImGui.PushStyleColor(ImGuiCol.Text, theme.greenDim)
    local nav = navPush()
    ImGui.Button(label)
    local clicked = mouseClicked()
    navPop(nav)
    ImGui.PopStyleColor(4)
    return clicked
end

-- A selectable row in the CRT list style.
function theme.selectable(label, selected)
    ImGui.PushStyleColor(ImGuiCol.Text, selected and theme.base or theme.greenDim)
    ImGui.PushStyleColor(ImGuiCol.Header, theme.greenMid)
    ImGui.PushStyleColor(ImGuiCol.HeaderHovered, theme.border)
    local nav = navPush()
    ImGui.Selectable(label, selected)
    local clicked = mouseClicked()
    navPop(nav)
    ImGui.PopStyleColor(3)
    return clicked
end

-- Single field input styled as a terminal entry line.
-- Returns the new text value. Callers emit their own caption above it.
function theme.input(label, current, maxlen)
    ImGui.PushStyleColor(ImGuiCol.FrameBg, theme.bg)
    ImGui.PushStyleColor(ImGuiCol.FrameBgHovered, theme.bg)
    ImGui.PushStyleColor(ImGuiCol.FrameBgActive, theme.bg)
    ImGui.PushStyleColor(ImGuiCol.Text, theme.base)
    local nav = navPush()
    local text, _ = ImGui.InputTextWithHint(label, ">_", current, maxlen)
    navPop(nav)
    ImGui.PopStyleColor(4)
    return text
end

-- Bottom status line.
function theme.statusbar(left, middle, right)
    ImGui.Spacing()
    theme.sep()
    theme.dim(left)
    if middle then
        local w = ImGui.GetItemRectSize() -- left item width
        ImGui.SameLine()
        theme.faint(middle)
    end
    if right then
        ImGui.SameLine()
        theme.text(right, theme.amber, 0.8)
    end
end

return theme