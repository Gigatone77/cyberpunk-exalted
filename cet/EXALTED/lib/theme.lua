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
theme.sky       = 0xFF3fb950 -- tOk green (unused links)
theme.amber     = 0xFFf5a623 -- tAccent warning / status
theme.red       = 0xFFf85149 -- tWarn errors
theme.white     = 0xFFffd479 -- tAccentHi bright headers
theme.base      = 0xFFe6edf3 -- tFg main text

-- Gold datapad palette used by the BOOK surface.
function theme.palette_gold()
    theme.green = 0xFFFFD98A
    theme.greenDim  = 0xFFC9A74F
    theme.greenMid  = 0xFF8A6D2A
    theme.greenFaint= 0xFF6B5520
    theme.border    = 0xFF3A2E0F
end

-- Restore the dark TUI palette used by the TERMINAL surface.
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

theme.font     = "Consolas"  -- decorative only; real font is CET's default

-- Format a dim terminal header line like "EXALTED TERMINAL 77 v0.1".
function theme.header(title, version, side)
    theme.text(title .. "  " .. version, theme.white)
    if side then
        ImGui.SameLine()
        theme.text(side, theme.greenDim)
    end
    theme.sep()
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

function theme.warn(text)
    theme.text(text, theme.amber, 0.95)
end

function theme.err(text)
    theme.text(text, theme.red, 0.95)
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

function theme.button(label)
    ImGui.PushStyleColor(ImGuiCol.Button, theme.panel)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, theme.greenMid)
    ImGui.PushStyleColor(ImGuiCol.ButtonActive, theme.border)
    ImGui.PushStyleColor(ImGuiCol.Text, theme.green)
    local clicked = ImGui.Button(label)
    ImGui.PopStyleColor(4)
    return clicked
end

function theme.buttonDim(label)
    ImGui.PushStyleColor(ImGuiCol.Button, theme.panel)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, theme.border)
    ImGui.PushStyleColor(ImGuiCol.ButtonActive, theme.border)
    ImGui.PushStyleColor(ImGuiCol.Text, theme.greenDim)
    local clicked = ImGui.Button(label)
    ImGui.PopStyleColor(4)
    return clicked
end

-- A selectable row in the CRT list style.
function theme.selectable(label, selected)
    ImGui.PushStyleColor(ImGuiCol.Text, selected and theme.base or theme.greenDim)
    ImGui.PushStyleColor(ImGuiCol.Header, theme.greenMid)
    ImGui.PushStyleColor(ImGuiCol.HeaderHovered, theme.border)
    local clicked = ImGui.Selectable(label, selected)
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
    local text, _ = ImGui.InputTextWithHint(label, ">_", current, maxlen)
    ImGui.PopStyleColor(4)
    return text
end

-- Push a styling block: returns a func that pops it. Canadian Usage:
-- local pop = theme.scrim(); ... ; pop()
function theme.scrim()
    ImGui.PushStyleColor(ImGuiCol.WindowBg, theme.bg)
    ImGui.PushStyleColor(ImGuiCol.Border, theme.border)
    ImGui.PushStyleColor(ImGuiCol.FrameBg, theme.bg)
    return function()
        ImGui.PopStyleColor(3)
    end
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