-- EXALTED Terminal 77: the terminal surface.
-- Tabbed CRT interface: [1 BROWSE] [2 SEARCH] [3 MEMORY] [4 NOTES] [5 ABOUT]

local theme = require("lib/theme")
local cache = require("lib/cache")

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

local M = {
    visible = false,
    tab = 1,
    booted = false,
    status = "INITIALIZING...",
    overlayOpen = false,
    suppressAuto = false,
    focusRequest = false,
    settingsLoaded = false,
    glass = 45,
    freeze = false,   -- opt-in: freeze the world while the terminal is interactive
    freezeOn = false, -- whether the EXALTED time-dilation channel is currently set
    focus = 2,        -- 1 BOOKS  2 VERSES  3 SEARCH  4 MEMORY  5 NOTES  6 ABOUT
    bookCursor = 0,   -- books rail highlight (0 = follow current book)
    resultSel = 0,    -- search result highlight
    noteSel = 0,      -- notes highlight

    -- browse
    books = {},
    book = 0,
    chapter = 1,
    totalChapters = 0,
    data = nil,          -- chapter payload
    selVerse = 0,
    selRef = "",
    noteBody = "",
    jumpBook = "",
    jumpChap = "",
    follow = false,      -- next draw recenters the selected verse (arrow nav)

    -- search
    query = "",
    searched = "",
    results = {},
    resultsBusy = false,

    -- memory
    cards = {},
    cardIdx = 0,
    shown = false,
    stats = { total = 0, due = 0, learning = 0, review = 0 },

    -- notes
    notes = {},
    newNoteRef = "",
    newNoteBody = "",
}

local TAB_BROWSE, TAB_SEARCH, TAB_MEMORY, TAB_NOTES, TAB_ABOUT = 1, 2, 3, 4, 5
local F_BOOKS, F_VERSES, F_SEARCH, F_MEMORY, F_NOTES, F_ABOUT = 1, 2, 3, 4, 5, 6
local PANEL_TAB = { [F_BOOKS] = TAB_BROWSE, [F_VERSES] = TAB_BROWSE, [F_SEARCH] = TAB_SEARCH,
    [F_MEMORY] = TAB_MEMORY, [F_NOTES] = TAB_NOTES, [F_ABOUT] = TAB_ABOUT }

-- FREEZE (opt-in) ----------------------------------------------------------
-- The terminal cannot stop the game receiving clicks/keys (CET's input trap
-- leaks under Proton), so "freeze" pins the world instead: while the terminal
-- is interactive we hold a dedicated time-dilation channel at ~0, so the game
-- still gets the input but nothing acts on it. Sandevistan and any other mod
-- use their own channels, so ours never clobbers them. Released on close,
-- overlay-close, script reload and shutdown.
local FREEZE_CHANNEL = "EXALTED_TERMINAL"
local FREEZE_VALUE = 0.0

local function freezeTimeSystem()
    local ok, ts = pcall(Game.GetTimeSystem)
    if ok and ts then return ts end
    return nil
end

function M.applyFreeze()
    local ts = freezeTimeSystem()
    if not ts then return end
    pcall(function() ts:SetTimeDilation(FREEZE_CHANNEL, FREEZE_VALUE) end)
end

function M.clearFreeze()
    local ts = freezeTimeSystem()
    if ts then pcall(function() ts:UnsetTimeDilation(FREEZE_CHANNEL) end) end
    M.freezeOn = false
end

-- Freeze only while the player can actually mouse around (overlay open), so a
-- read-only terminal left on screen never freezes Night City.
local function freezeSync()
    local want = (M.freeze and M.visible and M.overlayOpen) and true or false
    if want == M.freezeOn then return end
    if want then
        M.freezeOn = true
        M.applyFreeze()
    else
        M.clearFreeze()
    end
end

function M.setFreeze(on)
    M.freeze = on and true or false
    cache.setSetting("freeze", M.freeze)
    freezeSync()
end

function M.toggle()
    M.visible = not M.visible
    if M.visible then
        M.suppressAuto = false
        M.open()
    end
    freezeSync()
end

function M.onOverlayOpen()
    M.overlayOpen = true
    -- overlay open = the only time ImGui gets input (cursor + keys); make
    -- sure the terminal is up so it is immediately interactive.
    if not M.suppressAuto then
        M.visible = true
        M.open()
    end
    freezeSync()
end

function M.onOverlayClose()
    M.overlayOpen = false
    M.suppressAuto = false
    M.clearFreeze()
end

function M.setGlass(pct)
    M.glass = math.max(25, math.min(95, math.floor(pct)))
    theme.glass = M.glass / 100
    cache.setSetting("glass", M.glass)
end

function M.open()
    M.focusRequest = true
    if not M.settingsLoaded then
        M.settingsLoaded = true
        local g = cache.getSetting("glass", 45)
        M.setGlass(tonumber(g) or 45)
        M.freeze = cache.getSetting("freeze", false) and true or false
    end
    cache.boot(function(data)
        M.booted = true
        M.status = "READY — VERSION " .. tostring(data.active or "KJV")
        cache.getBooks(function(books)
            M.books = books
            if M.book == 0 and #books > 0 then
                M.book = books[1].n
            end
            M.gotoBook(M.book or 1, bookChapter(data), false)
        end)
    end)
    if M.tab == TAB_NOTES then refreshNotes() end
    if M.tab == TAB_MEMORY then refreshMemory() end
end

local function parseBookChapter(refstr)
    -- "Book C" or "Book C:V" -> (bookOrdinal, chapter) best-effort via books list
    if not refstr or refstr == "" then return nil end
    local num = refstr:match("(%d+)$")
    local name = refstr:gsub("%s*%d+[%d:]*$", ""):gsub("%s*%d+%s*$", "")
    if not num then return nil end
    for _, b in ipairs(M.books or {}) do
        if b.name == name or b.name:find(name, 1, true) == 1 then
            return b.n, tonumber(num)
        end
    end
    return nil
end

function bookChapter(data)
    local bm = data and data.bookmark or cache.bookmark
    local b, c = parseBookChapter(tostring(bm or ""))
    if b and c then return b, c end
    return 1, 1
end

function M.gotoBook(book, chapter, pushBookmark)
    M.book = book
    M.chapter = chapter or 1
    M.selVerse = 0
    M.selRef = ""
    if pushBookmark then
        local name = ""
        for _, b in ipairs(M.books) do
            if b.n == book then name = b.name break end
        end
        cache.setBookmark(name .. " " .. tostring(M.chapter))
    end
    cache.chapter(book, M.chapter, function(data)
        if data then
            M.data = data
            M.totalChapters = data.total_chapters or 0
            M.status = data.book_name .. " " .. tostring(data.chapter) .. " — LOADED"
        else
            M.status = "CHAPTER UNAVAILABLE"
        end
    end)
end

-- ---------------------------------------------------------------------------
-- keyboard navigation (only fires while CET overlay is open / input trapped)
-- ---------------------------------------------------------------------------

local KEY = ImGuiKey

local function typing()
    return ImGui.IsAnyItemActive()
end

local function verseCount()
    return (M.data and M.data.verses and #M.data.verses) or 0
end

function M.selectVerse(n)
    M.selVerse = n
    M.follow = true
    local d = M.data
    if d and n > 0 then
        M.selRef = string.format("%s %d:%d", d.book_name or "", d.chapter or 0, n)
    end
end

function bookStep(dir)
    for i, b in ipairs(M.books) do
        if b.n == M.book then
            local j = math.max(1, math.min(#M.books, i + dir))
            M.gotoBook(M.books[j].n, 1, true)
            return
        end
    end
    if #M.books > 0 then M.gotoBook(M.books[1].n, 1, true) end
end

local function chapterStep(dir)
    local i = 0
    for k, b in ipairs(M.books) do
        if b.n == M.book then i = k break end
    end
    if dir < 0 then
        if M.chapter > 1 then
            M.gotoBook(M.book, M.chapter - 1, true)
        elseif i > 1 then
            local prev = M.books[i - 1]
            M.gotoBook(prev.n, prev.chapters, true)
        end
    elseif dir > 0 then
        if M.totalChapters == 0 or M.chapter < M.totalChapters then
            M.gotoBook(M.book, M.chapter + 1, true)
        elseif i < #M.books then
            M.gotoBook(M.books[i + 1].n, 1, true)
        end
    end
end

local function doJump()
    local book = (M.jumpBook or ""):gsub("^%s+", ""):gsub("%s+$", "")
    local chap = (M.jumpChap or ""):gsub("^%s+", "")
    if book == "" and chap == "" then return end
    local b, c = M.book, tonumber(chap)
    if book ~= "" then
        local bl = book:lower()
        local hit
        for _, x in ipairs(M.books) do
            if x.name:lower() == bl or (x.short and x.short:lower() == bl) then hit = x break end
        end
        if not hit then
            local num = tonumber(book)
            if num and num >= 1 and num <= #M.books then hit = M.books[num] end
        end
        if not hit then M.status = "NO BOOK: " .. book return end
        b = hit.n
        if not c then c = 1 end
    end
    if not c or c < 1 then M.status = "CHAPTER?" return end
    local total = 0
    for _, x in ipairs(M.books) do
        if x.n == b then total = x.chapters or 0 break end
    end
    if total > 0 and c > total then c = total end
    M.gotoBook(b, c, true)
    M.jumpBook = ""
    M.jumpChap = ""
end

local function focusPanel(target)
    M.focus = target
    M.tab = PANEL_TAB[target] or M.tab
    if M.tab == TAB_SEARCH then refreshSearch() end
    if M.tab == TAB_NOTES then refreshNotes() end
    if M.tab == TAB_MEMORY then refreshMemory() end
end

local function currentBookIdx()
    if M.bookCursor > 0 then return M.bookCursor end
    for i, b in ipairs(M.books) do
        if b.n == M.book then return i end
    end
    return 1
end

-- Top bar is number-key only: 1 BROWSE · 2 SEARCH · 3 MEMORY · 4 NOTES ·
-- 5 ABOUT. Arrow keys are reserved for the two browse surfaces (books rail +
-- reading panel); TAB toggles focus between them and always returns to BROWSE.
local function navGlobal()
    if typing() then return end
    for i = 1, 5 do
        if ImGui.IsKeyPressed(KEY[tostring(i)]) then
            if i == 1 then
                M.focus = (M.focus == F_BOOKS or M.focus == F_VERSES) and M.focus or F_VERSES
                M.tab = TAB_BROWSE
            elseif i == 2 then
                focusPanel(F_SEARCH)
            elseif i == 3 then
                focusPanel(F_MEMORY)
            elseif i == 4 then
                focusPanel(F_NOTES)
            elseif i == 5 then
                focusPanel(F_ABOUT)
            end
        end
    end
    if ImGui.IsKeyPressed(KEY.Tab) then
        M.focus = (M.focus == F_BOOKS) and F_VERSES or F_BOOKS
        M.tab = TAB_BROWSE
    end
end

-- Per-panel arrow navigation. Only the books rail and the reading panel take
-- arrows; every other surface is pointer-driven.
local function navPanel()
    if typing() then return end
    if M.focus ~= F_BOOKS and M.focus ~= F_VERSES then return end

    if M.focus == F_BOOKS then
        local count = #M.books
        if count == 0 then return end
        if ImGui.IsKeyPressed(KEY.DownArrow, true) then
            M.bookCursor = math.min(count, currentBookIdx() + 1)
            return
        end
        if ImGui.IsKeyPressed(KEY.UpArrow, true) then
            M.bookCursor = math.max(1, currentBookIdx() - 1)
            return
        end
        if ImGui.IsKeyPressed(KEY.Enter) or ImGui.IsKeyPressed(KEY.RightArrow) then
            local b = M.books[currentBookIdx()]
            if b then
                M.gotoBook(b.n, 1, true)
                M.focus = F_VERSES
            end
            return
        end
        return
    end

    if M.focus == F_VERSES then
        if not M.data then return end
        local ctrl = ImGui.IsKeyDown(KEY.LeftCtrl) or ImGui.IsKeyDown(KEY.RightCtrl)
        if ctrl and ImGui.IsKeyPressed(KEY.LeftArrow) then bookStep(-1) return end
        if ctrl and ImGui.IsKeyPressed(KEY.RightArrow) then bookStep(1) return end
        if ImGui.IsKeyPressed(KEY.LeftBracket) then bookStep(-1) return end
        if ImGui.IsKeyPressed(KEY.RightBracket) then bookStep(1) return end
        if ImGui.IsKeyPressed(KEY.LeftArrow, true) then chapterStep(-1) return end
        if ImGui.IsKeyPressed(KEY.RightArrow, true) then chapterStep(1) return end
        local count = verseCount()
        if count == 0 then return end
        local n = M.selVerse
        if ImGui.IsKeyPressed(KEY.DownArrow, true) then
            M.selectVerse(n == 0 and 1 or math.min(count, n + 1))
            return
        end
        if ImGui.IsKeyPressed(KEY.UpArrow, true) then
            M.selectVerse(n <= 1 and 1 or (n == 0 and count or n - 1))
            return
        end
        if ImGui.IsKeyPressed(KEY.PageDown, true) then
            M.selectVerse(math.min(count, (n < 1 and 1 or n) + 10))
            return
        end
        if ImGui.IsKeyPressed(KEY.PageUp, true) then
            M.selectVerse(math.max(1, (n < 1 and count or n) - 10))
            return
        end
        if ImGui.IsKeyPressed(KEY.Home) then M.selectVerse(1) return end
        if ImGui.IsKeyPressed(KEY.End) then M.selectVerse(count) return end
        return
    end
end

-- ---------------------------------------------------------------------------
-- drawing
-- ---------------------------------------------------------------------------

function M.draw()
    if not M.visible then return end
    theme.palette_crt()
    theme.glass = M.glass / 100
    cache.poll(os.clock())
    freezeSync()
    navGlobal()

    local w, h = res()
    -- Resizable, centred, 80% by default (FirstUseEver = the player's own
    -- drag size persists; the lower-right grip and window edges resize).
    local winW, winH = math.floor(w * 0.8), math.floor(h * 0.8)
    ImGui.SetNextWindowPos(math.floor((w - winW) / 2), math.floor((h - winH) / 2), ImGuiCond.FirstUseEver)
    ImGui.SetNextWindowSize(winW, winH, ImGuiCond.FirstUseEver)
    ImGui.SetNextWindowSizeConstraints(640, 400, w, h)
    ImGui.PushStyleColor(ImGuiCol.WindowBg, theme.withAlpha(theme.bg, theme.glass))
    ImGui.PushStyleColor(ImGuiCol.Border, theme.withAlpha(theme.border, math.min(1, theme.glass + 0.15)))
    ImGui.PushStyleColor(ImGuiCol.FrameBg, theme.withAlpha(theme.bg, math.min(1, theme.glass + 0.05)))
    ImGui.PushStyleColor(ImGuiCol.FrameBgHovered, theme.withAlpha(theme.bg, math.min(1, theme.glass + 0.10)))
    ImGui.PushStyleColor(ImGuiCol.FrameBgActive, theme.withAlpha(theme.bg, math.min(1, theme.glass + 0.10)))
    ImGui.PushStyleColor(ImGuiCol.PopupBg, theme.withAlpha(theme.bg, 0.95))
    ImGui.PushStyleVar(ImGuiStyleVar.WindowBorderSize, 1)
    -- Our own arrow nav (books rail + reading panel) is the only keyboard nav
    -- we want; NoNavInputs/NoNavFocus stop ImGui's built-in nav from moving its
    -- highlight across the tab bar and lists by itself.
    local noNav = (ImGuiWindowFlags.NoNavInputs or 0) + (ImGuiWindowFlags.NoNavFocus or 0)
    -- Standard ImGui title bar: draggable to move, and the window resizes from
    -- every edge/corner (NoResize is NOT set). Raise it above other overlay
    -- windows whenever it is (re)opened so its buttons own the mouse.
    if M.focusRequest then
        ImGui.SetNextWindowFocus()
        M.focusRequest = false
    end
    if ImGui.Begin("EXALTED TERMINAL 77##exalted", ImGuiWindowFlags.NoCollapse + noNav) then
        drawHeader()
        drawTabs()
        navPanel()
        if M.tab == TAB_BROWSE then drawBrowse() end
        if M.tab == TAB_SEARCH then drawSearch() end
        if M.tab == TAB_MEMORY then drawMemory() end
        if M.tab == TAB_NOTES then drawNotes() end
        if M.tab == TAB_ABOUT then drawAbout() end
        drawStatus()
    end
    ImGui.End()
    ImGui.PopStyleVar()
    ImGui.PopStyleColor(6)
end

function drawHeader()
    local side = M.overlayOpen and "1-5 TABS · ARROWS IN BROWSE" or "OPEN CET OVERLAY TO INTERACT (KEYS)"
    theme.text("v0.1.3", theme.white)
    ImGui.SameLine()
    theme.text(side, theme.greenDim)
    theme.sep()
end

function drawTabs()
    local labels = { " 1 BROWSE ", " 2 SEARCH ", " 3 MEMORY ", " 4 NOTES ", " 5 ABOUT ", "   [X] CLOSE " }
    for i, label in ipairs(labels) do
        if i == 6 then
            ImGui.SameLine()
            if theme.button(label) then
                M.visible = false
            end
        else
            if i > 1 then ImGui.SameLine() end
            if theme.selectable(label, M.tab == i) then
                if i == TAB_BROWSE then
                    M.focus = (M.focus == F_BOOKS or M.focus == F_VERSES) and M.focus or F_VERSES
                    M.tab = TAB_BROWSE
                elseif i == TAB_SEARCH then
                    focusPanel(F_SEARCH)
                elseif i == TAB_MEMORY then
                    focusPanel(F_MEMORY)
                elseif i == TAB_NOTES then
                    focusPanel(F_NOTES)
                elseif i == TAB_ABOUT then
                    focusPanel(F_ABOUT)
                end
            end
        end
    end
    theme.sep()
end

-- BROWSE -----------------------------------------------------------------

function drawBrowse()
    theme.panelBegin("##br_cols", -1, -1)

    -- books rail (focused when the BOOKS panel has keyboard focus)
    ImGui.PushStyleVar(ImGuiStyleVar.ButtonTextAlign, 0.5, 0.5)
    theme.panelBegin("##br_books", 230, -1)
    for _, b in ipairs(M.books) do
        local hasCursor = (M.focus == F_BOOKS and b.n == M.book) or (M.focus == F_BOOKS and b.n == (M.books[currentBookIdx()] or {}).n)
        if theme.selectable(b.name, hasCursor) then
            M.gotoBook(b.n, 1, true)
            M.focus = F_VERSES
        end
    end
    if M.focus ~= F_BOOKS then
        theme.faint("TAB to books rail")
    else
        theme.faint("UP/DN book · ENTER open")
    end
    theme.panelEnd()
    ImGui.PopStyleVar()

    ImGui.SameLine()

    -- chapter page (focused when the VERSES panel has keyboard focus)
    theme.panelBegin("##br_page", -1, -1)
    drawChapterHeader()
    ImGui.Spacing()
    drawVerses()
    theme.panelEnd()

    theme.panelEnd()

    drawVerseActionBar()
end

function drawChapterHeader()
    local d = M.data
    ImGui.Text("")
    -- Title always shows the TARGET book/chapter (M.book/M.chapter), not the
    -- possibly-stale M.data payload still mid-load: prevents the "next then
    -- flicker to previous" impression when stepping chapters quickly.
    local name = d and d.book_name or ""
    for _, b in ipairs(M.books) do
        if b.n == M.book then name = b.name break end
    end
    theme.bright(name .. "  " .. tostring(M.chapter), 1.1)
    ImGui.SameLine()
    -- chapter buttons are MOUSE-ONLY: Enter/Space on a focused ImGui button
    -- can re-trigger a chapter step and look like a flicker backward.
    if theme.buttonDim("<") then chapterStep(-1) end
    ImGui.SameLine()
    theme.text(" CHAPTER " .. tostring(M.chapter) .. " / " .. tostring(M.totalChapters), theme.greenDim, 0.9)
    ImGui.SameLine()
    if theme.buttonDim(">") then chapterStep(1) end
    theme.sep()
    -- busy marker while the new chapter payload is loading
    if d and (d.chapter or 0) ~= M.chapter then
        theme.faint("LOADING " .. tostring(M.chapter) .. " ...")
        theme.sep()
    end
    -- jump bar: jump to a book and/or chapter (GO or Enter commits)
    theme.faint("BOOK")
    ImGui.SameLine()
    M.jumpBook = theme.input("##jb", M.jumpBook, 20)
    if ImGui.IsItemDeactivatedAfterEdit() then doJump() end
    ImGui.SameLine()
    theme.faint("CH")
    ImGui.SameLine()
    M.jumpChap = theme.input("##jc", M.jumpChap, 4)
    if ImGui.IsItemDeactivatedAfterEdit() then doJump() end
    ImGui.SameLine()
    if theme.button("GO") then doJump() end
    ImGui.SameLine()
    theme.faint("  <-  ->  chapter")
    theme.sep()
end

function drawVerses()
    theme.panelBegin("##br_verses", -1, -1)
    if not M.data or not M.data.verses or #M.data.verses == 0 then
        theme.faint("-- no verses loaded --")
        theme.panelEnd()
        return
    end
    for _, verse in ipairs(M.data.verses) do
        local name = M.data.book_name or ""
        ImGui.PushID(verse.v)
        -- keep the selected verse centered while arrow-navigating
        if verse.v == M.selVerse and M.follow then
            ImGui.SetScrollHereY(0.5)
        end
        -- verse number selectable gives the row's hit area + selection tint
        if theme.selectable(string.format("%3d", verse.v), M.selVerse == verse.v) then
            M.follow = false
            M.selectVerse(verse.v)
        end
        ImGui.SameLine()
        -- after the number, the verse text; red-letter spans stay in red
        local spans = verse.segs
        if not spans then spans = { { t = verse.text or "", r = false } } end
        local lineColor = (M.selVerse == verse.v) and theme.base or theme.greenDim
        for i, seg in ipairs(spans) do
            if seg.t and seg.t ~= "" then
                if i > 1 then ImGui.SameLine() end
                theme.text(seg.t, seg.r and theme.red or lineColor)
            end
        end
        ImGui.PopID()
    end
    M.follow = false -- one-shot recenter; free scrolling otherwise
    theme.panelEnd()
end

function drawVerseActionBar()
    if M.selRef == "" then
        theme.statusbar("SELECT A VERSE TO STUDY", nil, M.status)
        return
    end
    theme.sep()
    theme.dim("SELECTED :: " .. M.selRef)
    ImGui.SameLine()
    if theme.button("MEMORIZE") then
        cache.memoryAdd(M.selRef, function(data, err)
            M.status = err and ("MEMORY: " .. err) or ("ADDED TO DECK: " .. (data and data.ref or M.selRef))
        end)
    end
    ImGui.SameLine()
    if theme.button("NEW NOTE") then
        M.newNoteBody = ""
        M.noteFor = M.selRef
    end
    if M.noteFor then
        ImGui.Text("")
        theme.faint("NOTE FOR " .. M.noteFor)
        M.newNoteBody = theme.input("##note_body", M.newNoteBody, 500)
        ImGui.SameLine()
        if theme.button("SAVE") and M.newNoteBody ~= "" then
            local ref = M.noteFor
            cache.noteAdd(ref, M.newNoteBody, function(_, err)
                M.status = err and ("NOTE: " .. err) or ("NOTE SAVED — " .. ref)
                M.noteFor = nil
                M.newNoteBody = ""
            end)
        end
        ImGui.SameLine()
        if theme.buttonDim("CANCEL") then
            M.noteFor = nil
        end
    end
    theme.sep()
    theme.statusbar("CLICK OR PRESS ARROWS TO SELECT A VERSE", (M.data and (M.data.book_name .. " " .. tostring(M.data.chapter))) or "", M.status)
end

-- SEARCH -----------------------------------------------------------------

function drawSearch()
    theme.panelBegin("##sr_page", -1, -1)
    theme.bright("FULL-TEXT SEARCH", 1.1)
    theme.faint("Enter words or a phrase. Ranks shorter books first.")

    M.query = theme.input("##srq", M.query, 80)
    if M.query ~= M.searched and not M.resultsBusy and M.query ~= "" then
        refreshSearch()
    end
    ImGui.SameLine()
    if theme.button("SEARCH") then
        refreshSearch()
    end
    ImGui.SameLine()
    if theme.buttonDim("CLEAR") then
        M.query = ""
        M.searched = ""
        M.results = {}
    end

    ImGui.Spacing()
    M.suggestions()
    theme.sep()

    if #M.results == 0 then
        if M.searched == "" then
            theme.faint("Search across the active version.")
        else
            theme.dim("No results for \"" .. M.searched .. "\".")
        end
        theme.panelEnd()
        return
    end
    theme.panelBegin("##sr_results", -1, -1)
    for i, r in ipairs(M.results) do
        local label = string.format("%s %d:%d  —  %s", r.bookname, r.chapter, r.verse, r.text or "")
        local isSel = (M.focus == F_SEARCH and i == M.resultSel)
        if theme.selectable(label:sub(1, 110), isSel) then
            M.focus = F_SEARCH
            M.resultSel = i
            jumpToRef(r.book, r.chapter, r.verse, r.bookname)
        end
    end
    if M.focus == F_SEARCH then
        theme.faint("CLICK a result to open it")
    end
    theme.panelEnd()
    theme.panelEnd()
end

function refreshSearch()
    if M.query == "" then
        M.results = {}
        M.searched = ""
        return
    end
    if M.resultsBusy then return end
    M.resultsBusy = true
    M.searched = M.query
    cache.search(M.query, function(results)
        M.results = results or {}
        M.resultsBusy = false
    end)
end

-- Suggestions as quick words.
function M.suggestions()
    local words = {}
    if M.query and M.query ~= "" and not M.resultsBusy and #M.results == 0 then
        local short = M.query
        if #short >= 2 then
            local done = false
            cache.terms(short:lower(), function(terms)
                if done then return end
                done = true
                for i, t in ipairs(terms) do
                    if i > 6 then break end
                    words[#words + 1] = t.term
                end
            end)
        end
    end
    if #words > 0 then
        theme.faint("DID YOU MEAN?")
        for i, wd in ipairs(words) do
            ImGui.SameLine()
            if theme.buttonDim(wd) then
                M.query = wd
                M.searched = ""
                refreshSearch()
            end
        end
    end
end

function jumpToRef(book, chapter, verse, bookname)
    M.selVerse = verse
    M.selRef = string.format("%s %d:%d", bookname, chapter, verse)
    M.gotoBook(book, chapter, false)
    M.tab = TAB_BROWSE
end

-- MEMORY -----------------------------------------------------------------

function drawMemory()
    theme.panelBegin("##mem_page", -1, -1)
    theme.bright("SPACED REPETITION MEMORY", 1.1)
    if not typing() and #M.cards > 0 then
        if M.shown then
            if ImGui.IsKeyPressed(KEY.A) then gradeCard(0) end
            if ImGui.IsKeyPressed(KEY.H) then gradeCard(3) end
            if ImGui.IsKeyPressed(KEY.G) then gradeCard(4) end
            if ImGui.IsKeyPressed(KEY.E) then gradeCard(5) end
        elseif ImGui.IsKeyPressed(KEY.Space) then
            M.shown = true
        end
    end
    theme.dim(string.format("DECK %d  ·  DUE %d  ·  LEARNING %d  ·  REVIEW %d",
        M.stats.total, M.stats.due, M.stats.learning, M.stats.review))
    if theme.buttonDim("REFRESH") then
        refreshMemory()
    end
    ImGui.SameLine()
    if M.shown and #M.cards > 0 then
        if theme.button("NEXT") then
            advanceCard()
        end
    end
    theme.sep()

    if #M.cards == 0 then
        theme.faint("Nothing due right now.")
        theme.dim("STUDY FROM BROWSE: select a verse, then press MEMORIZE.")
        theme.panelEnd()
        return
    end

    local card = M.cards[M.cardIdx + 1]
    if card then
        theme.bright(card.refstr, 1.15)
        ImGui.Spacing()
        if M.shown then
            theme.textWrapped(card.text or "", theme.white, 1.0)
            ImGui.Spacing()
            theme.dim("GRADE:")
            ImGui.SameLine()
            if theme.button("A AGAIN") then gradeCard(0) end
            ImGui.SameLine()
            if theme.buttonDim("H HARD") then gradeCard(3) end
            ImGui.SameLine()
            if theme.buttonDim("G GOOD") then gradeCard(4) end
            ImGui.SameLine()
            if theme.buttonDim("E EASY") then gradeCard(5) end
        else
            theme.faint("(hidden)  ")
            ImGui.SameLine()
            if theme.button("REVEAL") then
                M.shown = true
            end
        end
        theme.faint(string.format("CARD %d / %d", M.cardIdx + 1, #M.cards))
    end
    theme.panelEnd()
end

function refreshMemory()
    cache.memoryStats(function(st)
        M.stats = st
    end)
    cache.memoryDue(function(cards)
        M.cards = cards or {}
        M.cardIdx = 0
        M.shown = false
    end)
end

function gradeCard(q)
    local card = M.cards[M.cardIdx + 1]
    if not card then return end
    cache.memoryGrade(card.refstr, q, function(_, err)
        M.status = err and ("MEMORY: " .. err) or ("GRADED " .. tostring(q) .. " — " .. card.refstr)
    end)
    M.cardIdx = M.cardIdx + 1
    M.shown = false
    if M.cardIdx >= #M.cards then
        M.cardIdx = 0
        refreshMemory()
    end
end

-- NOTES ------------------------------------------------------------------

function drawNotes()
    theme.panelBegin("##nt_page", -1, -1)
    theme.bright("STUDY NOTES", 1.1)
    theme.faint("Attach a note to any reference. Deletes move the note to trash (recoverable).")
    ImGui.Spacing()

    theme.faint("REF (e.g. John 3:16)")
    M.newNoteRef = theme.input("##nt_ref", M.newNoteRef, 40)
    theme.faint("NOTE BODY")
    M.newNoteBody = theme.input("##nt_body", M.newNoteBody, 500)
    ImGui.SameLine()
    if theme.button("ADD") and M.newNoteRef ~= "" and M.newNoteBody ~= "" then
        local ref = M.newNoteRef
        cache.noteAdd(ref, M.newNoteBody, function(_, err)
            M.status = err and ("NOTE: " .. err) or ("NOTE SAVED — " .. ref)
            M.newNoteRef = ""
            M.newNoteBody = ""
            refreshNotes()
        end)
    end
    theme.sep()

    if #M.notes == 0 then
        theme.faint("No notes yet.")
        theme.panelEnd()
        return
    end
    theme.panelBegin("##nt_list", -1, -1)
    for i, n in ipairs(M.notes) do
        local isSel = (M.focus == F_NOTES and i == M.noteSel)
        if theme.selectable(n.ref, isSel) then
            M.focus = F_NOTES
            M.noteSel = i
            local b, c = parseBookChapter(n.ref)
            if b and c then
                jumpToRef(b, c, n.verse or 1, n.ref:match("%S+"):lower():gsub("^%l", string.upper) or "")
            end
        end
        ImGui.SameLine()
        if theme.buttonDim("DEL") then
            cache.noteRemove(n.ref, function(_, err)
                M.status = err and ("NOTE: " .. err) or ("NOTE TRASHED — " .. n.ref)
                refreshNotes()
            end)
        end
        theme.textWrapped("     " .. (n.body or ""), theme.greenDim, 0.95)
    end
    if M.focus == F_NOTES then
        theme.faint("CLICK a note to open it")
    end
    theme.panelEnd()
    theme.panelEnd()
end

function refreshNotes()
    cache.notesList(function(notes)
        M.notes = notes or {}
    end)
end

-- ABOUT ------------------------------------------------------------------

local function totalVerses(books)
    local n = 0
    for _, b in ipairs(books) do
        n = n + (b.verses or 0)
    end
    return n
end

function drawAbout()
    theme.panelBegin("##ab_page", -1, -1)
    theme.bright("EXALTED TERMINAL 77", 1.15)
    theme.dim("Offline King James Bible reader, study deck, and notes inside Cyberpunk 2077.")
    theme.sep()
    theme.text("ENGINE  CET (pure Lua)", theme.greenDim)
    theme.text("VERSION " .. tostring(cache.activeVersion), theme.greenDim)
    theme.text("DATA    " .. tostring(#cache.canon) .. " books · " .. tostring(totalVerses(cache.canon)) .. " verses", theme.greenDim)
    theme.text("LOAD    ONLINE", theme.green)
    theme.sep()
    theme.dim("DISPLAY — GLASS (SEE-THROUGH)")
    ImGui.SameLine()
    if theme.buttonDim("-") then M.setGlass(M.glass - 5) end
    ImGui.SameLine()
    theme.text(string.format("%3d%%", M.glass), theme.white, 0.9)
    ImGui.SameLine()
    if theme.buttonDim("+") then M.setGlass(M.glass + 5) end
    ImGui.SameLine()
    if theme.buttonDim("RESET") then M.setGlass(45) end
    theme.faint("lower = more of Night City shows through the terminal")
    theme.sep()
    theme.dim("WORLD — FREEZE WHILE TERMINAL IS INTERACTIVE")
    ImGui.SameLine()
    if theme.buttonDim(M.freeze and " ON " or " OFF") then M.setFreeze(not M.freeze) end
    theme.faint("on = pin world time so stray clicks/keys cannot act on V")
    theme.faint("     (EXALTED-only time-dilation channel; released when you close)")
    theme.sep()
    theme.faint("RESIZE  drag the lower-right corner or any window edge")
    theme.sep()
    theme.faint("KEYS    1-5 switch the top bar (BROWSE · SEARCH · MEMORY · NOTES · ABOUT)")
    theme.faint("        TAB toggles BOOKS <-> VERSES · arrows work in those two only:")
    theme.faint("        BOOKS: UP/DN book, ENTER open · VERSES: UP/DN verse,")
    theme.faint("        <- -> chapter, PgUp/PgDn ±10, HOME/END")
    theme.faint("        SEARCH/MEMORY/NOTES are pointer-driven (click an item)")
    theme.faint("        (MEMORY) SPACE reveal, A/H/G/E grade")
    theme.faint("OPEN CET OVERLAY to mouse around (cursor + clicks appear there)")
    theme.faint("HOTKEY   assign in CET Overlay -> Bindings -> EXALTED")
    theme.faint("DATA     fully local KJV seeded in the mod folder (no network)")
    theme.faint("LEGACY   notes & memory live in the isolated game copy")
    theme.panelEnd()
end

-- STATUS -----------------------------------------------------------------

function drawStatus()
    local panel = { [F_BOOKS] = "BOOKS", [F_VERSES] = "VERSES", [F_SEARCH] = "SEARCH",
        [F_MEMORY] = "MEMORY", [F_NOTES] = "NOTES", [F_ABOUT] = "ABOUT" }
    local hint = "FOCUS: " .. (panel[M.focus] or "?") .. " · 1-5 tabs · TAB books<->verses · arrows in BROWSE"
    if M.overlayOpen then hint = hint .. " · MOUSE LIVE" end
    theme.statusbar(hint, M.status, M.booted and "READY" or "BOOTING")
end

return M