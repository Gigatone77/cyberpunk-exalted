# EXALTED Terminal 77

An offline King James Bible reader and spaced-repetition study deck that lives
inside Cyberpunk 2077 as a CET (Cyber Engine Tweaks) Lua mod.

Two surfaces:

- **EXALTED TERMINAL** — a full-screen CRT terminal opened with a hotkey.
  Five tabs: Browse (read any book/chapter, select a verse),
  Search (full-text), Memory (spaced-repetition review), Notes, About.

Everything is **fully local**: the King James Bible is bundled as JSON in
`<mod>/data/` (books.json, kjv/*.json, terms.json). Notes, memory cards, and
bookmarks live only as small JSON files in the mod folder. No network, no host
process, nothing touches your desktop `~/.biblelearn` collection.

## How it works

| Piece        | Where                        | What it does                            |
|--------------|------------------------------|------------------------------------------|
| CET Lua mod  | `<game>/.../cyber_engine_tweaks/mods/EXALTED/` | ImGui UI + hotkeys |
| Data layer   | `<mod>/data/`                | JSON assets read directly by CET Lua (`json.decode` + mod-relative `io.open`) |
| Persistence  | `<mod>/*.json`               | bookmark, notes, notes_trash, memory deck |

No bridge binary, no external process. All engine ops (books, chapters, search,
terms, notes, memory) are synchronous Lua callbacks in `lib/cache.lua`.

## Build & install

```bash
# 1) Export KJV data (needs the Go toolchain in ~/.local/go/bin)
cd Games/biblelearn && ./cmd/bibleexport -out ../../cyberpunk-exalted/cet/EXALTED/data

# 2) Package the mod as a single Nexus-style zip
cd cyberpunk-exalted && ./scripts/package.sh

# 3) Install: extract the zip into the game root
unzip dist/EXALTED_Terminal_77-0.1.0.zip -d ~/Games/Cyberpunk\ 2077/
```

Then in-game: open the **CET Overlay** (Ctrl+Tab by default) → Bindings →
bind a key for `OPEN EXALTED TERMINAL`.

## Requirements

- Cyber Engine Tweaks (CET) for CP2077 x64
- No host binary required — pure Lua, ships inside the mod folder

## License & credits

- Bible text: King James Version (Authorized Version) 1611 / Oxford 1769 —
  **public domain** outside the UK printing patent (Project Gutenberg,
  Crosswire/eBible.org). No copyrighted modern-spelling edition is used.
- CET (MIT) and Dear ImGui (MIT) are used only through their public APIs —
  no framework source is bundled.
- All other code (Lua mod, Go exporter, scripts, docs) is original.
Full provenance: `docs/CREDITS.md`.

## Files

```
cet/EXALTED/
  init.lua          hotkeys, on_draw dispatch
  lib/cache.lua     pure-CET data layer (books, chapters, notes, memory)
  lib/theme.lua     CRT/phosphor palette + ImGui helpers
  ui/terminal.lua   5-tab terminal surface (browse, search, memory, notes, about)
  data/
    books.json      66-book canon (n, name, short, chapters, verses)
    kjv/            66 JSON files (one per book: chapters → verses with red segs)
    terms.json      term index for suggestions
```

A datapad "THE BOOK" surface is prototyped but parked at
`cet/book-prototype/ui/book.lua` — not shipped.
