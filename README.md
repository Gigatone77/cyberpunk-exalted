# EXALTED Terminal 77

An offline King James Bible reader and spaced-repetition study deck that lives
inside Cyberpunk 2077. Two independent surfaces from one JSON dataset:

- **EXALTED TERMINAL** — a full-screen CRT terminal opened with a hotkey
  (CET Lua mod). Five tabs: Browse (read any book/chapter, select a verse),
  Search (full-text), Memory (spaced-repetition review), Notes, About.
- **EXALTED BROWSER SITE** — the whole Bible inside the in-game browser
  (redscript + Browser Extension Framework, Nexus mod 10038). Browse to
  `NETdir://exalted.terminal`; 66 books / 1189 chapters / 31102 verses,
  red-letter words of Christ. See `docs/BROWSER-SITE.md`.

Everything is **fully local**: the King James Bible is bundled as JSON in
`<mod>/data/` (books.json, kjv/*.json, terms.json) and compiled to redscript
for the browser surface (`internet/EXALTED/data/` via
`scripts/gen-exalted-reds.py`). Notes, memory cards, and bookmarks live only
as small JSON files in the mod folder. No network, no host process, nothing
touches your desktop `~/.biblelearn` collection.

## How it works

| Piece        | Where                        | What it does                            |
|--------------|------------------------------|------------------------------------------|
| CET Lua mod  | `<game>/.../cyber_engine_tweaks/mods/EXALTED/` | ImGui UI + hotkeys |
| Browser site | `<game>/r6/scripts/EXALTED/` | redscript site for the in-game browser (`NETdir://exalted.terminal`) |
| Data layer   | `<mod>/data/`                | JSON assets read directly by CET Lua (`json.decode` + mod-relative `io.open`) |
| Data→reds    | `scripts/gen-exalted-reds.py`| compiles the JSON into redscript book modules |
| Persistence  | `<mod>/*.json`               | bookmark, notes, notes_trash, memory deck |

No bridge binary, no external process. All engine ops (books, chapters, search,
terms, notes, memory) are synchronous Lua callbacks in `lib/cache.lua`.

## Build & install

```bash
# 1) Export KJV data (needs the Go toolchain in ~/.local/go/bin)
cd Games/biblelearn && ./cmd/bibleexport -out ../../cyberpunk-exalted/cet/EXALTED/data

# 2) Regenerate the redscript browser data (from the same JSON)
cd cyberpunk-exalted && python3 scripts/gen-exalted-reds.py

# 3) Package — three Nexus-style zips in dist/:
#      EXALTED_Terminal_77-0.1.5.zip         (CET + browser, unified)
#      EXALTED_Terminal_77-CET-0.1.5.zip     (CET surface only)
#      EXALTED_Terminal_77-Browser-0.1.2.zip (browser site only)
cd cyberpunk-exalted && ./scripts/package.sh

# 4) Install: extract the unified zip into the game root
unzip dist/EXALTED_Terminal_77-0.1.5.zip -d ~/Games/Cyberpunk\ 2077/
```

Browser framework note: the browser site needs **Cyberpunk 2077 Browser
Extension Framework** (Nexus mod 10038) installed. Without it the site's
listener compiles to a no-op and simply isn't listed.

Then in-game: open the **CET Overlay** (Ctrl+Tab by default) → Bindings →
bind a key for `OPEN EXALTED TERMINAL`. For the browser site, power on any
computer, open a browser, choose **Exalted Terminal 77**.

## Requirements

- Cyber Engine Tweaks (CET) for CP2077 x64
- Browser Extension Framework (Nexus mod 10038) — for the browser site only
- No host binary required — pure Lua + pure redscript, ships in the mod folders

## License & credits

- Bible text: King James Version (Authorized Version) 1611 / Oxford 1769 —
  **public domain** outside the UK printing patent (Project Gutenberg,
  Crosswire / eBible). No copyrighted modern-spelling edition is used.
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

internet/EXALTED/         browser surface (redscript)
  Site.reds               site listener + router + page builders (module ExaltedSite)
  data/ExaltedData.reds   generated master (66 imports)
  data/ExaltedBook01-66.reds   generated chapter text per book
scripts/gen-exalted-reds.py    generates internet/EXALTED/data from cet/EXALTED/data
```

A datapad "THE BOOK" surface is prototyped but parked at
`cet/book-prototype/ui/book.lua` — not shipped.
