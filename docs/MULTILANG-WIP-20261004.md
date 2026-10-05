# EXALTED multi-language pack — WIP hand-off (2026-10-04)

**STATUS: PAUSED BY USER, ON PURPOSE. Do the in-game verify FIRST, then finish this.**

Order is now fixed by user decision (2026-10-04):

1. **In-game verify** the English browser surface (see `~/Projects-Pending.txt` #18).
2. **Finish this multi-language pack.**
3. Then the accessible Bible catalog.

Nothing here has ever rendered on screen. Do not ship a multi-language zip
before step 1 tells us the base surface works at all.

---

## What is DONE and verified

### The hard constraint that dictated the design
REDScript module names are **flat file basenames** across all of `r6/scripts` and
`r6/tweaks`. A German `ExaltedBook01.reds` and a Czech `ExaltedBook01.reds` are
the *same module name* — the second silently wins, and you ship a pack where the
language picker lies. Directories do **not** namespace modules. So per-language
packaging as planned (drop `ExaltedBook01Deu.reds` next to `ExaltedBook01Cze.reds`)
**cannot work as written.** Suffixing is the only reliable namespacing.

### `scripts/langify.py` (new, working)
Takes the six already-verified `data/` trees and emits one combined tree where
every module and public symbol carries a language suffix.

- `ExaltedBook01.reds` → `ExaltedBook01En.reds`, func `ExaltedBook01Chapter` → `ExaltedBook01EnChapter`
- `ExaltedData.reds` → `ExaltedDataEn.reds` (+ new `ExaltedChapterTotalEn()`)
- `ExaltedUiEn.reds` — per-language UI string table, `ExaltedUiStrEn(key)`
- `ExaltedLang.reds` — combined dispatcher: language list, code/endonym/English
  name, per-language book name/short/chapter-count/chapter-text/totals, UI strings

**Only names are rewritten.** String literals are copied byte-for-byte and the
script *proves it* per file (`literals()` compare, aborts on any difference), so
every Bible verification result carries over unchanged. This script never parses
scripture.

Run:
```
scripts/stage_lang_trees.sh                     # reproducible staging
scripts/langify.py --stage <stage> --out <out>
```

### `scripts/stage_lang_trees.sh` (new, working)
Reproducible staging of the six shippable trees from the **verified artifacts**,
never from `bible-sources/raw` (immutable). Asserts 66 book modules per language.
Verified byte-identical to the hand-staged tree.

- en ← `internet/EXALTED/data`
- cze/deu/dut/pol ← `~/bible-sources/site/<code>/data`
- **es ← `dist/EXALTED_Terminal_77-Browser-es-0.1.2.zip`** — Spanish has *no*
  `bible-sources/site/es` tree; the shipped zip is the verified artifact. This is
  why the pack takes the suffix route rather than a site-tree rebuild.

### `translations/ui.json` (new, complete for 6 languages)
23 UI keys × 6 languages, localized book names already baked into each tree.

Edition lines are **transcribed from each source's own in-file metadata**, never
guessed:

| lang | source | edition line basis |
|---|---|---|
| en | KJV | 1769 |
| es | RV1909 printed PDF | `docs/RV1909-SOURCE.md`, sha256 `1d8545c5…` |
| cze | `cze-bkr.zefania.xml` | description: *posledního vydání Kralického z roku 1613* |
| deu | `deu-luther1912.osis.xml` | description: *Lutherbibel von 1912* |
| dut | `dut-statenvertaling.zefania.xml` | *Dutch Statenvertaling* — **no edition year in file, so no year shown** |
| pol | `PolUGdanska-osis.json` | module PolUG (Gdańska), text dated 1838 |

---

## Two real bugs this work found — do not regress them

### 1. The English stats line is a lie for 5 of 6 languages
`Site.reds` hardcoded `s"66 Books / 1189 Chapters / 31102 Verses"`. Actual
per-language verse totals:

| lang | books | chapters | verses | red-letter |
|---|---|---|---|---|
| en | 66 | 1189 | 31102 | **2028** |
| es | 66 | 1189 | 31102 | 0 |
| cze | 66 | 1189 | **31172** | 0 |
| deu | 66 | 1189 | **31171** | 0 |
| dut | 66 | 1189 | **31079** | 0 |
| pol | 66 | 1189 | 31102 | 0 |

Only English has red letters (2028). The stats line **must** be computed at
runtime from `ExaltedLangVerseTotal(l)` etc., and the red-letter legend must be
gated on `ExaltedLangRedTotal(l) > 0` — otherwise Spanish/Czech/German/Dutch/
Polish pages claim red letters they do not have and print wrong counts.

### 2. `ExaltedLangOfCode` first emitted invalid redscript
The generator produced `switch code { case 0: if Equals(...) … }`. A `switch`
whose cases contain `if` statements is **not valid redscript**. Fixed to a plain
`if`-chain. Guard against regressing it: the tree must contain no
`case <n>: if ` anywhere.

---

## What is NOT done

1. **`Site.reds` is still English-only and hardcoded.** It still calls
   `ExaltedBookName()` / `ExaltedChapterText()` / `ExaltedBookChapterCount()`
   from the unsuffixed `ExaltedData`, imports `ExaltedData.*` directly, and
   hardcodes all 23 chrome strings. It must be rewritten to:
   - `import ExaltedLang.*` + `import ExaltedUi.*`
   - dispatch through `ExaltedLang*(this.EXAL_Lang(), …)`
   - replace chrome literals with `EXAL_S(key)` lookups into `ExaltedUiLangStr`
   - build the stats line from runtime totals, gate red-letter text on red > 0
   - **add the `/lang` route** + a persisted current-language value, and a
     language link in the header/footer
   - resolve a short (`Gen`) to a language-specific short **per selected language**
2. **Language persistence.** No storage exists yet. The site has no
   `RebuildStorage`/settings code today — decide where the current language lives
   (`RebuildStorage`, a user-settings node, or a `NETdir` path segment).
3. **`package.sh` cannot build the multi zip.** Add a `multilang` mode that
   packs `ExaltedLang.reds` + all suffixed trees + the rewritten `Site.reds`.
4. **Per-language packs also need rebuilding** if `Site.reds` is unified, because
   their modules gain a suffix. That is a version bump: browser `0.1.2` → `0.1.3`,
   unified `0.1.5` → `0.1.6`. Nothing is tested in-game, so there is no
   compatibility cost to doing it now.
5. **No in-game verification of anything**, in any language.
6. **Non-Latin still blocked** — `Site.reds:175` hardcodes Raj; see
   `docs/FONT-ROUTE.md`.

---

## Cost, now measured

6 languages × 1189 chapters = **7,134 chapter literals**, ~6,950 dispatchable
literals, **21.5 MB**. Comfortably inside what redscript handles. This is the
number that killed the archive backend (`docs/MULTILINGUAL-PLAN.md` §5.0, §5.3.1):
ArchiveXL cannot read strings out of an archive member at all, only register
archives/dirs and patch whole resource files, so the "move the text out of
literals" plan was never buildable — and at this size it is not needed.