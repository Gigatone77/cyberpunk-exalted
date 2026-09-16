-- EXALTED Terminal 77: the BOOK surface.
-- A datapad/reader for flowing scripture reading (Chapter page view), distinct
-- gold chrome. Opens into your bookmarked position. Click a verse to memorize
-- or take a note; chapter changes auto-save the bookmark.

local theme = require("lib/theme")
local cache = require("lib/cache")
local terminal = require("ui/terminal")

local W, H = { got = false }

local function res()
    if W.got then return W.w, W.h end
    local ok, a, b = pcall(Game.GetResolution)
    if ok and type(a) == "number" and type(b) == "number" and a > 0 and b > 0 then
        W.w, W.h, W.got = a, b, true
    else
        W.w, W.h, W.got = 1920, 1080, true
    end
    return W.w, W.h
end

local gold = {
    text   = 0xFFFFD98A,
    dim    = 0xFFC9A74F,
    faint  = 0xFF6B5520,
    border = 0xFF3A2E0F,
}

local M = {
    visible = false,
    booted = false,
    bootFailed = false,

    books = {},
    book = 1,
    chapter = 1,
    totalChapters = 0,
    data = nil,

    selVerse = 0,
    selRef = "",
    mark = "",          -- current saved mark ref
    reading = "",       -- "Book C"
    status = "INITIALIZING...",
}

-- Custom book palette overrides on the shared terminal modules.
function M.theme()
    theme.palette_gold()
end

local function parseBookChapter(refstr)
    if not refstr or refstr == "" then return nil end
    local num = refstr:match("(%d+)$")
    local name = refstr:gsub("%s*%d+[%d:]*$", "")
    if not num then return nil end
    for _, b in ipairs(M.books or {}) do
        if b.name == name or b.name:find(name, 1, true) == 1 then
            return b.n, tonumber(num)
        end
    end
    return nil
end

function M.toggle()
    M.visible = not M.visible
    if M.visible then M.open() end
end

function M.open()
    M.bootFailed = false
    cache.boot(function()
        M.booted = true
        cache.getBooks(function(books)
            M.books = books
            M.openChapter(true)
        end)
    end)
    -- If the bridge answers but boot already fired earlier, refresh anyway.
    if cache.booted and #M.books > 0 then
        M.openChapter(true)
    end
end

function M.openChapter(followMark)
    local b, c
    if followMark then
        b, c = parseBookChapter(tostring(cache.bookmark))
        if not b or not c then
            if #M.books > 0 then b, c = M.books[1].n, 1 end
        end
    else
        b, c = M.book, M.chapter
    end
    if not b then return end
    M.book = b
    M.chapter = c or 1
    M.selVerse = 0
    M.selRef = ""
    for _, bk in ipairs(M.books) do
        if bk.n == M.book then M.reading = bk.name .. " " .. tostring(M.chapter) end
    end
    cache.chapter(M.book, M.chapter, function(data)
        if not data then
            M.status = "CHAPTER UNAVAILABLE"
            return
        end
        M.data = data
        M.totalChapters = data.total_chapters or 0
        M.status = "OPEN  " .. data.book_name .. " " .. tostring(data.chapter)
        -- Only autosave a mark on user navigation (followMark=False), never
        -- while just opening.
        if not followMark then
            M.mark = data.book_name .. " " .. tostring(data.chapter)
            cache.setBookmark(M.mark)
        else
            M.mark = cache.bookmark or ""
        end
    end)
end

function M.goToChapter(c)
    if c < 1 or (M.totalChapters > 0 and c > M.totalChapters) then return end
    M.chapter = c
    M.openChapter(false)
end

-- ---------------------------------------------------------------------------
-- drawing
-- ---------------------------------------------------------------------------

function M.draw()
    if not M.visible then return end
    cache.poll(os.clock())
    M.theme()

    local w, h = res()
    ImGui.SetNextWindowPos(0, 0, ImGuiCond.Always)
    ImGui.SetNextWindowSize(w, h, ImGuiCond.Always)
    ImGui.PushStyleColor(ImGuiCol.WindowBg, theme.bg)
    ImGui.PushStyleColor(ImGuiCol.Border, theme.border)
    ImGui.PushStyleColor(ImGuiCol.FrameBg, theme.bg)
    if ImGui.Begin("##EXALTED_BOOK", ImGuiWindowFlags.NoTitleBar + ImGuiWindowFlags.NoResize + ImGuiWindowFlags.NoMove) then
        drawHeader()
        drawBody()
        drawFooter()
    end
    ImGui.End()
    ImGui.PopStyleColor(3)
end

function drawHeader()
    theme.header("EXALTED  ◆  THE BOOK", "READER", "datapad mode")
    ImGui.SameLine()
    ImGui.PushStyleColor(ImGuiCol.Text, gold.text)
    ImGui.Text("   [X] CLOSE")
    ImGui.PopStyleColor()
    if ImGui.IsItemClicked() then
        M.visible = false
    end
    theme.sep()
end

function drawBody()
    theme.panelBegin("##bk_body", -1, -1)

    -- reading pane
    theme.panelBegin("##bk_page", -1, -1)
    if not M.data then
        theme.faint("-- the book is silent --")
    else
        theme.text(M.reading, gold.text, 1.15)
        theme.text("CHAPTER " .. tostring(M.data.chapter) .. " OF " .. tostring(M.data.total_chapters), gold.dim, 0.9)
        theme.sep()
        for _, verse in ipairs(M.data.verses or {}) do
            local label = string.format("%d.  %s", verse.v, verse.text or "")
            if theme.selectable(label, M.selVerse == verse.v) then
                M.selVerse = verse.v
                M.selRef = string.format("%s %d:%d", M.data.book_name, M.data.chapter, verse.v)
            end
        end
        if M.selRef and M.selRef ~= "" then
            theme.sep()
            theme.dim("MARKED :: " .. M.selRef)
            ImGui.SameLine()
            if theme.button("MEMORIZE") then
                cache.memoryAdd(M.selRef, function(_, err)
                    M.status = err and ("MEMORY: " .. err) or ("ADDED TO DECK — " .. M.selRef)
                end)
            end
            ImGui.SameLine()
            if theme.button("NOTE") then
                terminal.open()
                terminal.tab = 4
                terminal.newNoteRef = M.selRef
                M.visible = false
            end
        end
    end
    theme.panelEnd()

    ImGui.SameLine()

    -- chapter rail
    theme.panelBegin("##bk_rail", 170, -1)
    theme.faint("CHAPTERS")
    for c = 1, M.totalChapters do
        if theme.selectable(tostring(c), c == M.chapter) then
            M.goToChapter(c)
        end
    end
    theme.panelEnd()

    theme.panelEnd()
end

function drawFooter()
    ImGui.Spacing()
    theme.sep()
    theme.faint("MARK  " .. (M.mark ~= "" and M.mark or "—"))
    if #M.books == 0 then return end

    if theme.buttonDim("< PREV CH") then
        if M.totalChapters == 0 or M.chapter > 1 then
            M.goToChapter(M.chapter - 1)
        end
    end
    ImGui.SameLine()
    if theme.buttonDim("HOME") then
        M.openChapter(true)
    end
    ImGui.SameLine()
    if theme.button("NEXT CH >") then
        if M.totalChapters == 0 or M.chapter < M.totalChapters then
            M.goToChapter(M.chapter + 1)
        end
    end
    ImGui.SameLine()
    theme.text(M.status, gold.dim, 0.9)
end

return M