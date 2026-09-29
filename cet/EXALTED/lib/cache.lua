-- EXALTED Terminal 77: pure-CET data layer.
--
-- Reads the bundled KJV JSON directly from <mod>/data (books.json,
-- kjv/<ordinal>.json, terms.json) with CET's built-in json + io.open -- no
-- bridge, no external process. Bookmarks, notes, and the spaced repetition
-- deck persist as small JSON files next to the mod.

local cache = {
    booted = false,          -- a boot reply fired at least once
    app = "exalted",
    appVersion = "0.1.0",
    activeVersion = "KJV",
    versions = {},           -- [{ id, name, books, complete, builtin }]
    bookmark = "",           -- e.g. "Psalm 23"
    canon = {},              -- { n, name, short, chapters, verses }[]
    bookIndex = {},          -- name (lower) -> ordinal

    booksData = {},          -- ordinal -> decoded kjv/<n>.json chapter table
    chapters = {},           -- "book:chapter" -> { book, chapter, verses, ... }
    termsList = nil,         -- decoded terms.json (lazy)

    -- settings (UI prefs like glass opacity)
    settings = {},

    -- persistence
    notes = {},
    memory = {},             -- ref -> { ref, text, interval, ease, reps, state, due }

    -- indexing (search needs every book loaded; stepped across frames)
    indexQueue = nil,        -- nil = not started, {} = done
    indexCbs = {},
}

local M = cache

local FS = {
    bookmark = "exalted_bookmark.json",
    notes = "exalted_notes.json",
    notesTrash = "exalted_notes_trash.json",
    memory = "exalted_memory.json",
    settings = "exalted_settings.json",
}

local function jsonRead(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local s = f:read("*a")
    f:close()
    if not s or s == "" then return nil end
    local ok, v = pcall(json.decode, s)
    if not ok or type(v) ~= "table" then return nil end
    return v
end

local function jsonWrite(path, v)
    local ok, s = pcall(json.encode, v)
    if not ok then return false end
    local f = io.open(path, "w")
    if not f then return false end
    f:write(s)
    f:close()
    return true
end

local function canon()
    if #M.canon > 0 then return M.canon end
    local list = jsonRead("data/books.json") or {}
    M.canon = {}
    M.bookIndex = {}
    for _, b in ipairs(list) do
        M.canon[#M.canon + 1] = b
        if type(b.name) == "string" then M.bookIndex[b.name:lower()] = b.n end
        if type(b.short) == "string" then M.bookIndex[b.short:lower()] = b.n end
    end
    return M.canon
end

function M.init()
    canon()
    local bm = jsonRead(FS.bookmark)
    if bm and bm.ref then M.bookmark = bm.ref end
    M.notes = jsonRead(FS.notes) or {}
    local mem = jsonRead(FS.memory)
    if type(mem) == "table" then M.memory = mem end
    local st = jsonRead(FS.settings)
    if type(st) == "table" then M.settings = st end
end

-- Small settings/prefs store (glass opacity, etc.).
function M.getSetting(key, dflt)
    local v = M.settings[key]
    if v == nil then return dflt end
    return v
end

function M.setSetting(key, val)
    M.settings[key] = val
    jsonWrite(FS.settings, M.settings)
end

-- Boot is synchronous now (all data is local).
function M.boot(onReady)
    local data = { active = "KJV", bookmark = M.bookmark }
    if M.booted then
        if onReady then pcall(onReady, data) end
        return data
    end
    M.booted = true
    M.activeVersion = "KJV"
    M.versions = { { id = "KJV", name = "King James Version (1611)", books = #M.canon, complete = true, builtin = true } }
    if onReady then pcall(onReady, data) end
    return data
end

-- Books canon (sync; cached).
function M.getBooks(cb)
    local out = canon()
    if cb then cb(out) end
    return out
end

local function strip_margins(text)
    -- Drop trailing KJV margin/cross-reference apparatus ("+ 8.6 drawn: Heb.
    -- pulled", "+ 1.20 Mara: that is, Bitter") that rides on verse text. The
    -- generator applies the same strip to the browser data; mirror it here so
    -- the terminal never renders margin notes as body text. Source files
    -- (data/kjv/*.json) are never modified; the strip happens on the decoded
    -- copy only.
    if type(text) ~= "string" then return text end
    local s, e = text:find("%+ %d+%.%d+ ")
    if s then return text:sub(1, s - 1) end
    return text
end

local function loadBook(ord)
    if M.booksData[ord] then return M.booksData[ord] end
    local t = jsonRead("data/kjv/" .. tostring(ord) .. ".json")
    if type(t) == "table" then
        for _, verses in pairs(t) do
            for _, v in ipairs(verses or {}) do
                if v and type(v) == "table" then
                    if v.text then v.text = strip_margins(v.text) end
                    if v.segs then
                        for _, seg in ipairs(v.segs) do
                            if seg and seg.t then seg.t = strip_margins(seg.t) end
                        end
                    end
                end
            end
        end
    else
        t = nil
    end
    M.booksData[ord] = t
    return t
end

local function chapterCount(book)
    local n = 0
    for _ in pairs(book or {}) do n = n + 1 end
    return n
end

function M.chapter(bookOrd, chapter, cb)
    local key = tostring(bookOrd) .. ":" .. tostring(chapter)
    local got = M.chapters[key]
    if got then
        if cb then cb(got) end
        return got
    end
    local book = loadBook(tonumber(bookOrd))
    local verses = book and book[tostring(chapter)]
    if not verses then
        if cb then cb(nil) end
        return nil
    end
    local b = canon()[tonumber(bookOrd)]
    local out = {
        book = bookOrd,
        chapter = chapter,
        book_name = (b and b.name) or tostring(bookOrd),
        total_chapters = chapterCount(book),
        verses = verses,
    }
    M.chapters[key] = out
    if cb then cb(out) end
    return out
end

local function parseRef(ref)
    -- "Book C" / "Book C:V" (best effort via canon)
    if not ref or ref == "" then return nil end
    local c, v = ref:match("(%d+):(%d+)$")
    local name
    if c then
        name = ref:gsub("%s*%d+:%d+$", "")
    else
        c = ref:match("(%d+)$")
        name = ref:gsub("%s*%d+$", "")
    end
    if not c then return nil end
    local ord = M.bookIndex[(name or ""):lower()]
    if not ord then
        local nl = (name or ""):lower()
        for _, b in ipairs(canon()) do
            if b.short and nl == b.short:lower() then ord = b.n break end
        end
    end
    if not ord then return nil end
    return ord, tonumber(c), tonumber(v)
end

function M.read(ref, cb)
    local ord, ch, v = parseRef(ref)
    if not ord then
        if cb then cb(nil, "unknown reference") end
        return nil
    end
    local data = M.chapter(ord, ch or 1)
    if not data then
        if cb then cb(nil, "unknown reference") end
        return nil
    end
    local verse
    for _, x in ipairs(data.verses) do
        if x.v == (v or 1) then verse = x break end
    end
    local out = { book = ord, chapter = ch, verse = v or 1, bookname = data.book_name }
    if verse then
        out.text = verse.text
        out.segs = verse.segs
    end
    if cb then cb(out, nil) end
    return out
end

-- Full-text search. Every book must be decoded first; stepped in poll().
function M.search(query, cb)
    local q = (query or ""):lower()
    local tokens = {}
    for tok in q:gmatch("'?[%w]+'?") do
        tokens[#tokens + 1] = tok
    end
    if #tokens == 0 then
        if cb then cb({}) end
        return
    end
    local run = function()
        local results = {}
        for ord = 1, #M.canon do
            local book = M.booksData[ord]
            if book then
                local bname = M.canon[ord].name
                for cnum, verses in pairs(book) do
                    for _, verse in ipairs(verses) do
                        local tlow = (verse.text or ""):lower()
                        local hit = true
                        for _, tok in ipairs(tokens) do
                            if not tlow:find(tok, 1, true) then hit = false break end
                        end
                        if hit then
                            results[#results + 1] = {
                                book = ord, chapter = tonumber(cnum), verse = verse.v,
                                bookname = bname, text = verse.text or "",
                            }
                            if #results >= 24 then
                                if cb then cb(results) end
                                return
                            end
                        end
                    end
                end
            end
        end
        if cb then cb(results) end
    end
    if M.indexQueue == nil or #M.indexQueue > 0 then
        M.indexCbs[#M.indexCbs + 1] = run
        if M.indexQueue == nil then
            M.indexQueue = {}
            for ord = 1, #M.canon do
                if not M.booksData[ord] then M.indexQueue[#M.indexQueue + 1] = ord end
            end
        end
    else
        run()
    end
end

-- Term suggestions from terms.json (already sorted by count desc).
function M.terms(prefix, cb)
    if M.termsList == nil then
        M.termsList = jsonRead("data/terms.json") or {}
    end
    local p = (prefix or ""):lower()
    local out = {}
    for _, t in ipairs(M.termsList) do
        if type(t.term) == "string" and t.term:sub(1, #p) == p then
            out[#out + 1] = t
            if #out >= 12 then break end
        end
    end
    if cb then cb(out) end
    return out
end

function M.setVersion(id, cb)
    M.activeVersion = "KJV"
    if cb then cb({ active = "KJV", versions = M.versions }) end
end

function M.setBookmark(ref)
    M.bookmark = ref
    jsonWrite(FS.bookmark, { ref = ref })
end

function M.getBookmark(cb)
    if cb then cb(M.bookmark) end
    return M.bookmark
end

-- Notes ------------------------------------------------------------------
function M.notesList(cb)
    if cb then cb(M.notes) end
    return M.notes
end

function M.noteAdd(ref, body, cb)
    local verse = tonumber((ref or ""):match(":(%d+)$") or 1)
    local replaced = nil
    for i, n in ipairs(M.notes) do
        if n.ref == ref then
            replaced = table.remove(M.notes, i)
            break
        end
    end
    M.notes[#M.notes + 1] = { ref = ref, body = body, verse = verse, ts = os.time(), updated = (replaced and replaced.ts or os.time()) }
    jsonWrite(FS.notes, M.notes)
    if cb then cb({ ref = ref }, nil) end
end

-- Deletes move the note to trash (recoverable), never destroy it.
function M.noteRemove(ref, cb)
    for i, n in ipairs(M.notes) do
        if n.ref == ref then
            local gone = table.remove(M.notes, i)
            local trash = jsonRead(FS.notesTrash) or {}
            gone.trashed_at = os.time()
            trash[#trash + 1] = gone
            jsonWrite(FS.notesTrash, trash)
            jsonWrite(FS.notes, M.notes)
            if cb then cb({ ref = ref }, nil) end
            return
        end
    end
    if cb then cb(nil, "note not found") end
end

-- Memory (SM-2, mirroring store.ScheduleNext) ---------------------------
local function clamp(v, lo, hi)
    if v < lo then return lo end
    if v > hi then return hi end
    return v
end

function M.memoryStats(cb)
    local now = os.time()
    local total, due, learning, review = 0, 0, 0, 0
    for _, c in pairs(M.memory) do
        total = total + 1
        if c.due and c.due <= now then due = due + 1 end
        if c.state == 1 then learning = learning + 1 end
        if c.state == 2 then review = review + 1 end
    end
    local out = { total = total, due = due, learning = learning, review = review }
    if cb then cb(out) end
    return out
end

function M.memoryDue(cb)
    local now = os.time()
    local cards = {}
    for _, c in pairs(M.memory) do
        if c.due and c.due <= now then cards[#cards + 1] = c end
    end
    table.sort(cards, function(a, b) return a.due < b.due end)
    local out = {}
    for i = 1, math.min(30, #cards) do
        out[#out + 1] = cards[i]
    end
    if cb then cb(out) end
    return out
end

function M.memoryAdd(ref, cb)
    local data = M.read(ref)
    if not data or not data.text then
        if cb then cb(nil, "verse not found") end
        return
    end
    local card = M.memory[ref] or {}
    card.ref = ref
    card.refstr = ref
    card.text = data.text
    card.interval = 0
    card.ease = 2.5
    card.reps = 0
    card.state = 0
    card.due = os.time() + 600 -- first review in 10 minutes
    M.memory[ref] = card
    jsonWrite(FS.memory, M.memory)
    if cb then cb({ ref = ref }, nil) end
end

function M.memoryGrade(ref, quality, cb)
    local card = M.memory[ref]
    if not card then
        if cb then cb(nil, "card not in deck") end
        return
    end
    local q = tonumber(quality) or 0
    local now = os.time()
    if card.state == 0 then
        card.reps = 0
        card.interval = 0
        card.state = 1
        card.due = now + 600
    elseif card.state == 1 then
        if q == 0 then
            card.ease = clamp(card.ease - 0.15, 1.3, 3.5)
            card.interval = 0
            card.due = now + 600
        else
            card.reps = card.reps + 1
            card.interval = 1
            card.state = 2
            card.due = now + 86400
        end
    else -- state 2 review
        if q == 0 then
            card.ease = clamp(card.ease - 0.20, 1.3, 3.5)
            card.interval = 0
            card.state = 1
            card.due = now + 600
        else
            card.ease = clamp(card.ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)), 1.3, 3.5)
            if card.reps == 0 then
                card.interval = 1
            elseif card.reps == 1 then
                card.interval = 6
            elseif q >= 4 then
                card.interval = card.interval * card.ease
            else
                card.interval = card.interval * 1.2
            end
            card.reps = card.reps + 1
            card.due = now + math.floor(card.interval * 86400)
        end
    end
    jsonWrite(FS.memory, M.memory)
    if cb then cb({ ref = ref }, nil) end
end

-- Stepped background book decoding (driven from on_draw).
function M.poll(now)
    if M.indexQueue == nil or #M.indexQueue == 0 then return end
    for _ = 1, 2 do
        local ord = table.remove(M.indexQueue, 1)
        loadBook(ord)
        if #M.indexQueue == 0 then break end
    end
    if #M.indexQueue == 0 then
        local cbs = M.indexCbs
        M.indexCbs = {}
        for _, cb in ipairs(cbs) do
            pcall(cb)
        end
    end
end

-- No-op: kept for interface parity with the old bridge layer.
function M.keepalive() end
function M.bridgeOK() return true end

return M
