# EXALTED Terminal — Architecture

## Pure Lua, no bridge

```
┌───────────────────────────────────────┐
│  Cyberpunk 2077 (Wine/Proton)         │
│                                       │
│  CET Lua mod (EXALTED)                │
│  ImGui surfaces + hotkeys             │
│                                       │
│  lib/cache.lua  ← JSON read via       │
│  data/kjv/*.json    CET io.open       │
│  data/books.json    + json.decode     │
│  data/terms.json                     │
│                                       │
│  Persistence files (next to mod):     │
│    exalted_bookmark.json              │
│    exalted_notes.json                 │
│    exalted_notes_trash.json           │
│    exalted_memory.json                │
└───────────────────────────────────────┘
```

Everything runs inside CET's Lua sandbox. No bridge binary, no external
process, no network. The KJV data ships as clean JSON in `<mod>/data/`
and is decoded with CET's built-in `json.decode`. A second datapad
surface ("THE BOOK") is prototyped at `cet/book-prototype/ui/book.lua`
but not shipped.

## Lua module map

- `init.lua`: registers the hotkey, calls `cache.init()` on game load,
  `cache.poll(os.clock())` on every frame to step the search preloader,
  and draws `terminal.draw()` when the UI is visible.
- `lib/cache.lua`: synchronous data layer. Boot is immediate (all JSON is
  local). Books, chapters, search, terms, notes, and memory operations
  all return results in the same frame. Search uses a frame-stepped
  background index (2 books per frame) so the UI stays responsive.
- `lib/theme.lua`: ImGui color/style helpers using only primitives proven
  in installed CET mods (`PushStyleColor`, `Text*`, `Selectable`,
  `BeginChild`, `InputTextWithHint`, `SetWindowFontScale`). Palette is
  the EXALTED dark CRT scheme.
- `ui/terminal.lua`: five-tab terminal (Browse, Search, Memory, Notes,
  About). Browse rows render verse numbers + red-letter spans inline.
  Memory cards are SM-2 spaced repetition; notes are keyed by ref.

## Data format

### books.json
Array of `{ n, name, short, chapters, verses }` — one entry per OT/NT
book in canonical order (66 books total). `verses` = total verse count
for the book.

### kjv/<n>.json
Per-book object keyed by chapter string. Each chapter is an array of
`{ v, text, segs[] }` where `v` is the verse number and `text` is the
full verse string. `segs` (when present) is an array of
`{ t, r }` where `r=true` marks words of Christ in red.

Red letter segmentation is done at export time by the Go USFM exporter
(`cmd/bibleexport/main.go`) which strips `\wj...\wj*` tags and attaches
an `r=true` flag to the enclosed segment. Clean text: no footnotes, no
strong codes, no `\p`/`\c`/`\v` markup.

### Persistence files
- `exalted_bookmark.json` — `{ ref: "Psalm 23" }`
- `exalted_notes.json` — array of `{ ref, body, verse, ts, updated }`
- `exalted_notes_trash.json` — trashed notes (recoverable, never auto-deleted)
- `exalted_memory.json` — ref→card map with `{ ref, refstr, text, interval,
  ease, reps, state, due }` (SM-2; scheduling mirrors the Go bridge exactly)

## Hotkeys

CET tracks an id→keycode map (`bindings.json`, 0 = unbound). The mod
registers `OPEN_EXALTED_TERMINAL`; users bind the key in the CET Overlay.
Nothing is auto-bound to avoid clashing with the game.
