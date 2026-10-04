# EXALTED Browser Site — redscript surface (Sep 18)

A second surface of EXALTED Terminal 77: the **whole KJV readable inside
the in-game Browser**. This is a **redscript-only** site for the
**Browser Extension Framework** (Nexus mod **10038**), a C++ framework
that lets mods register custom `NETdir://` sites into the vanilla in-game
browser. No CET, no Lua.

## Install

Unzip `EXALTED_Terminal_77-Browser-0.1.1.zip` (or the unified
`EXALTED_Terminal_77-0.1.4.zip`) into the game root — it lands at
`r6/scripts/EXALTED/`. Requires the Browser Extension Framework already
installed (`r6/scripts/BrowserExtension/`). Redscript compiles on game
launch (full game restart required, not just reload).

You browse to the site from any in-game browser: address
`NETdir://exalted.terminal`, title **Exalted Terminal 77** (zetatech1 icon).
The site appears on the browser's site list when the player powers on a
computer with a browser app.

> Fallback: if the Browser Extension Framework is NOT installed, the whole
> `ExaltedSite` listener falls back to a no-op stub so the file still
> compiles (`@if(!ModuleExists("BrowserExtension.System"))`). Ship both
> paths; users without the framework just won't see the site.

## File map

```
internet/EXALTED/               repo source (game-relative r6/scripts/EXALTED/)
  Site.reds                     module ExaltedSite — listener, router, page builders
  data/ExaltedData.reds         generated: ExaltedBookTotal/Name/Short/ChapterCount/ChapterText
  data/ExaltedBook01-66.reds    66 generated book modules (chapter text as strings)
scripts/gen-exalted-reds.py     generator: cet/EXALTED/data (JSON) -> above
```

Generated modules are named `ExaltedBookNN` (NN = 01..66) so there are no
tokens to sanitize in module names, only in string literals.

## Generated data encoding

Each chapter's text is stored as one `String` literal. 66 books / 1189
chapters / 31102 verses / 2028 red-letter verses = 67 data files, 1390
string literals. Encoding inside a chapter string:

- verse separator: `{|}`   → `EXAL_Split(s, "{|}")` gives `[vnum, body,
  vnum, body, …]` (odd indexes, step 2)
- line separator:  `{~}`   → split a verse body on `{~}` for one `inkText`
  per source line (respects the exporter's paragraph breaks)
- red-letter:      `{r}`…`{/r}`  → one line wrapped; `EXAL_RedLine` strips
  the 3-char open / 4-char close; `EXAL_NewText(…, red=true)` colors it
- wrap width 76 chars, so no single literal exceeds ~16KB (Psalm 119 is
  the largest at 15789 chars — fine for redscript's `String`)

All delimiters are checked at generation: any literal `{`, `}`, `~` in the
source would collide, so the generator rejects the source if found. `¶` is
checked too — `strip_margins()` owns that glyph (USFM section marker, 2970
verses across 42 books) plus the dangling colon left by a removed margin note,
and any survivor fails generation rather than shipping. `strip_margins()` is
mirrored in `cet/EXALTED/lib/cache.lua` for the CET surface; the two must stay
byte-identical in behaviour (verified over all 31828 corpus segments).

## Site routes

`NETdir://exalted.terminal` + suffix:

| Route | Page |
|---|---|
| `/`            | home (name, counts, links) |
| `/about`       | about box |
| `/books[/<pg>]`| 66-book paginated list, 8/page (`EXAL_BOOKS_PER_PAGE`) |
| `/b/<short>[/<pg>]` | chapter list for a book, 10/page (`EXAL_CHAPS_PER_PAGE`) |
| `/r/<short>/<ch>:<vp>` | reader, 10 **lines**/page (`linesPerPage`), not verses (vp = page, 0-based) |

> Reader sizing uses **static values** (Sep 18): 10 rows/page, body font 42,
> verse numbers 40, page sub 44, nav links 40 — fills more of the width (76-char
> generated lines render wider at 42) and more of the height (10 lines/page).
> A runtime page_content-measurement approach was tried and reverted (no
> visible effect). Headers stay top-left; menu buttons stay centered.

Reader footer: chapter-page prev/next, prev/next chapter, `CHAPTERS`,
`HOME`. Word of Christ lines render in red (`HDRColor(1.0, 0.2941, 0.2941)`);
verse numbers are dimmed (`0.5450, 0.5803, 0.6196`); links highlight amber
on hover. Widget names embed the destination address, so the shared click
callback (`EXAL_OnLinkClicked`) routes via `NameToString(w.GetName())` →
`LoadPageByAddress` — no per-link userdata objects.

## Anchor points used from the framework (all confirmed in the installed build)

- `BrowserEventsListener` (base class), `Init(logic)` / `Uninit()`,
  `GetWebPage(address) -> ref<inkCompoundWidget>`
- `system.Register` / `system.Unregister` (via base class)
- `BrowserGameController.LoadPageByAddress` (loaded on the
  `m_deviceLogicController` field), `OnInitialize/OnUninitialize`
  lifecycle via `@addField` + `@wrapMethod`
- Site appears on the browser home page automatically: the framework's
  `GetCustomSites()` polls every registered listener's `GetSiteData()`
  (address + shortName + zetatech1 icon), so no manual remap is needed —
  mirror CJ's `Init` (set `m_siteData.address`/`shortName` after
  `super.Init`)

## Redscript API notes (verified against installed mods)

- `SetInteractive(true)` is REQUIRED on an `inkText`/`inkWidget` before
  `RegisterToCallback(n"OnRelease"/n"OnHoverOver"/…)` — missing it means
  click/hover callbacks never fire (fixed Sep 18).
- `StringToInt(s, default)` two-arg form, `IntToString`, `NameToString`,
  `StringToName`, `StrAfterFirst`, `StrBeginsWith`, `StrMid`, `StrLen`,
  `StrFindFirst`, `Clamp`, `ArraySize`/`ArrayPush`, `Equals`, and Int32
  `/`/`%` are all used by installed redscript mods — no exotic procs.

## Interop with the CET surface

Independent: the CET terminal (`bin/x64/…/mods/EXALTED/`) and this
redscript site (`r6/scripts/EXALTED/`) share the same JSON source
(`cet/EXALTED/data`) but ship separately, so each works without the other.
Generate both from one dataset; the unified zip simply contains both trees.