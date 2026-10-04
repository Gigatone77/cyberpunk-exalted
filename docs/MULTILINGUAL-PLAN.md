# EXALTED Terminal 77 — Multilingual Expansion Plan

Status: **P0 SHIPPED (Spanish RV1909, Oct 4) — see §8.** Sections 1–7 are the
original plan, written after the Oct 4 fixed-source purge + push to `main`
(`2c27df4`), and are retained as the design record; §8 records what actually
shipped and where the plan was wrong. Remaining languages: planning only.

Scope requested: **Browser editions** in additional languages, using the most
authoritative version the user approves per language, with **no Catholic /
"apostate" source text**.

---

## 1. Hard constraints (decided before any code)

| # | Constraint | Consequence |
|---|---|---|
| C1 | **Never** delete/move/overwrite/re-encode any Bible file. Source data stays pristine; cleanup happens only at render time (existing `¶`/margin rule). | Desktop PDFs stay untouched. Converters read, never write, the originals. |
| C2 | **Absolutely no Catholic-source translations.** | Portuguese ACF **excluded**. So are Italian CEI, Spanish Reina-Valera Catholic ed., German Catholic Einheitsübersetzung, French NBS/LSG-CE, Polish NRSV, etc. Excluded by source lineage, not merely by name. |
| C3 | Only text that can legally ship on Nexus + a public GitHub repo. | Effectively **public-domain** (pre-1929 / non-copyrighted). Verified per language in §4. |
| C4 | "Most authoritative" = the user's accepted standard version for that language. | Table in §4 is a **proposal**, not a decision. User signs off per language. |
| C5 | Per-language Bible preservation floor (existing rule): keep >=1 authentic Holy-text copy per language forever. | Applies to what we ingest: if we ship a language, its source is also archived to the Bible locations. |
| C6 | No force-push / history rewrite; generated artifacts get `.sha256`; everything mirrored to staging + ToolBox. | Same release discipline as 0.1.x. |

---

## 2. What the browser actually is (verified in-repo, Oct 4)

`internet/EXALTED/Site.reds`:

- registers `NETdir://exalted.terminal` via the **Browser Extension Framework**
  (Nexus **10038**, `BrowserExtension.System`), redscript-only, no CET/Lua;
  the whole listener is wrapped in `@if(ModuleExists(...))` with a no-op stub.
- builds real `inkCanvas` / `inkText` widgets — **the game's own text renderer**.
- **hardcodes the font family** at `Site.reds:175`:
  `SetFontFamily("base\\gameplay\\gui\\fonts\\raj\\raj.inkfontfamily")`
  (Rajdhani — a Latin display face), with `Regular`/`Bold` styles.
- data = generated `.reds` string literals: **67 files, 1390 literals, 4.5 MB**
  (66 book modules + `ExaltedData.reds`).

### 2.1 Rendering is the real risk, not translation

The game ships **19 text localizations** (CDPR-supported): English, French,
Italian, German, Spanish, Brazilian Portuguese, Polish, Russian, Japanese,
Simplified + Traditional Chinese, Korean, Arabic, Czech, Hungarian, Turkish,
Thai, Ukrainian (+ variants). So Latin, Cyrillic, CJK, Arabic and Thai scripts
exist in the game **somewhere**.

Two unknowns we cannot resolve statically:

1. **Does the `raj` ink font family fall back to CJK/Arabic/Thai glyphs?** The
   game almost certainly uses a *different* family for CJK locales. If `raj`
   has no fallback, Japanese/Chinese/Korean/Arabic/Thai text renders as tofu
   through our mod. Cheap decisive test: switch game language to Japanese/Arabic,
   open `NETdir://exalted.terminal`, look.
2. **Hebrew is not a game language** -> no glyphs, no shaping. Hebrew needs a
   custom ink atlas (RTL + niqqud is hard; consonants-only Hebrew is doable).

Mitigation for (1): a per-language font-family map in `Site.reds` (e.g. use the
game's CJK family for zh/ja/ko, Arabic family for ar) instead of the hardcoded
Rajdhani. Mitigation for (2): P3 phase, ship glyphs in an ink atlas via the
`Cyberpunk-Helper-Scripts` `generate_inkatlas.py` workflow.

---

## 3. Data pipeline (same for every language)

Source of truth stays the **canonical JSON** per language (what `kjv/*.json` is
today). Converter = `scripts/convert_usfm.py` (NEW, stdlib only):

```
USFM/OSIS/PDF-text source (read-only)
  -> convert_usfm.py  ->  <lang>/<NN>.json   { "ch": [{v, text}, ...] }
                      ->  books-<lang>.json [{n, name, short, chapters, verses}]
  -> gen-exalted-reds.py (EXISTING) -> internet/EXALTED-<LANG>/data/*.reds
```

Target schema is trivial and already proven (verified `kjv/62.json`):

```json
{ "1": [ {"v": 1, "text": "..."}, {"v": 2, "text": "..."} ] }
```

`books.json`: `{"n":1,"name":"Genesis","short":"Gen","chapters":50,"verses":1533}`

**Book names per language** come from the USFM `\h1` heading (or the PDF book
heading) — we never ship English book names with a foreign text.

### 3.1 Cleanup parity (C1)

The existing KJV cleanup strips USFM pilcrows `¶`, the dangling colon whose
note was removed, and `+ N.N` margin apparatus — implemented **twice** in
parity (`gen-exalted-reds.py` and `cet/EXALTED/lib/cache.lua`), asserted by
`check_bad`. Other source formats need their **own** rules, each parity-tested:

- USFM: `\p`/`\q` paragraphs (keep), `\\` line breaks, `\rem`, superscript
  footnote markers `\s ... \f` (Crosswire notes — strip or keep? **decision**).
- Japanese: `\ide` (ideographic) paragraphs; no pilcrows in Shinkaiyaku.
- CJK: no interword spaces -> wrapping must not rely on spaces (§5.3).

---

## 4. Per-language source + licensing matrix (Spanish row SIGNED OFF; rest is PROPOSAL)

Legend: PD = public domain, shippable. Blocked = not shippable / not acceptable.

| Language | Proposed version | Machine-readable source | License | Verdict |
|---|---|---|---|---|
| English | **KJV 1611 / Oxford 1769** (shipped) | Crosswire/eBible USFM; local `English-PDF.zip` = same | PD | ship (current) |
| English | **NKJV 1982** | only a **PDF** on disk | **© Thomas Nelson — NOT shippable** | text only, do not redistribute |
| Spanish | **Reina-Valera 1909** — **APPROVED + SHIPPED Oct 4** | **printed PDF `Documents/20/Bibles/Spanish.zip`** (authority) | PD | **shipped** (`EXALTED_Terminal_77-Browser-es-0.1.2.zip`) |
| Spanish | ~~eBible `spaRV1909` USFM~~ | — | PD | **REJECTED as shippable text** — see note below. Audit witness only. |
| Spanish | Reina-Valera 1960/1979 | eBible `spaRVR1960` | © | blocked |
| Portuguese | **Pre-1898 Almeida** (APPROVED) | seven1m `por-almeida.usfx.xml` | PD | **ship P2** |
| Portuguese | ACF / ARC | local zips | — | **EXCLUDED by user (C2)** |
| Japanese | **Shinkaiyaku 1970** | local `Japanese.zip` (66 PDFs) + eBible `jpnshink` | PD | ship P2 (C/font test first) |
| Hebrew | SDA / BHS (TBD) | local `Hebrew.zip` (66 PDFs) | BHS © (SHS) | **blocked — version + font** |
| French | **Louis Segond 1910** | eBible `fraLSG` USFM | PD | ship P1 |
| German | **Luther 1912** / Elberfelder 1906 | seven1m/open-bibles | PD | ship P1 |
| Russian | **Synodal 1876** | eBible `RUSSYN` | PD | ship P2 (Cyrillic) |
| Italian | **Riveduta 1927** | seven1m / eBible `ita-riveduta` | PD | ship P1 |
| Dutch | **Statenvertaling 1637** | seven1m `dut-statenvertaling` | PD | ship P1 |
| Polish | **Updated Gdansk** / Lubomersch | seven1m `pol-*` | PD | ship P1 |
| Czech | **Bible kralicka** | seven1m `cze-kralicka` | PD | ship P1 |
| Korean | Korean Revised (gokyeok) | seven1m `kor-*` | PD-ish | ship P2 |
| Chinese | **CUV 1919** (and/or) | eBible / hbfuller `zh-*` | PD | ship P2 |
| Arabic | **Van Dyck 1865/1920** | eBible `arb-vd` | PD | ship P2 (RTL+shaping test) |
| Hungarian | **Karoli 1590** | seven1m | PD | ship P1 |
| Turkish | TBD (ATS 2001?) | — | uncertain | research |
| Thai | TBD (LPT) | — | uncertain | research |
| Ukrainian | TBD | — | uncertain | research |

> **Do NOT "upgrade" the Spanish build back to the eBible USFM.** This plan
> originally assumed `Spanish.zip` (the PDFs) and `spaRV1909` USFM were the same
> text and listed the USFX as the machine-readable source. They are not. The
> eBible / wordproject / BibleAquifer RV1909 digital text silently **shifts
> chapters** (Job 40 runs 5 verses long; Números 12:16 lands at 13:1), has **18
> empty verse targets**, and all three providers share **one corrupted scan
> lineage**. It is rebuilt by `scripts/rv1909/reconstruct_digital_es.py` as an
> **audit witness only**. The printed PDF is the shipping authority; the digital
> line exists solely to diff against. Full detail: `docs/RV1909-SOURCE.md`.
> Any other language in this table that relies on a provider USFX must be
> checked for the same failure mode before it is trusted.

Rejected by C2 anywhere in the chain: ACF, CEI, NBS, Einheitsübersetzung,
Einheitsübersetzung 2016, RSV-Catholic, NRSV-CE, Spanish BIC, Korean Catholic
(RVCRM = Catholic Revised Version — explicitly excluded even though Korean RV).

**Mandatory verification per language before shipping:** 66 books / chapter+verse
counts match the canonical KJV counts (1189 chapters / 31102 verses) except
where the version legitimately differs (e.g. Hebrew/ deuterocanonical books),
the USFM parses without silent verse loss, license text is stored in
`docs/CREDITS.md`, and a sha256 of the exact source file is recorded.

---

## 5. Packaging architecture — BOTH (user decision, Oct 4)

User answer: *"one per language and a multi language. one also."* -> ship **both**:

**A. Per-language pack** (`EXALTED_Terminal_77-<LANG>-<VER>.zip`)
- Installs to `r6/scripts/EXALTED/`, contains that language's data + site code.
- Replaces the English data of that surface. No code changes needed for the
  reader; redscript compiles only the language present.
- Cost: ~4.5 MB + 67 files + 1390 literals **per installed language only**.

**B. One multi-language pack** (`EXALTED_Terminal_77-MultiLang-<VER>.zip`)
- All approved languages + an in-website **language index page** (new route
  `/lang` in `Site.reds`; language code in the path, e.g. `/es/b/42`).
- Requires `Site.reds` changes: language state, per-language book names, UI
  strings, font-family selection (§2.1), and per-script wrapping (§5.3).
- Cost: 19 x 4.5 MB = **~85 MB, ~25k string literals**, long redscript compile.
- **Mitigation that becomes near-mandatory here:** move scripture text out of
  `.reds` string literals into an **`.archive` resource** per language, read via
  ArchiveXL (option C below). That keeps the compile fast and memory sane.
  This is the single biggest engineering item of the whole project.

**C. Text backend = `.archive` resource instead of `.reds` literals**
- Per-language text resource read at page-build time; literals vanish.
- Same proven mechanism as `pattern.archivexl-resource-replace` already in the
  GigaPunk/GigaData notes: an `.archive` member at a base-game resource path
  overrides it wholesale.
- Needed for B, optional for A.

### 5.0 Per-language budget (measured from English)
| Item | Per language |
|---|---|
| browser data | 4.5 MB, 67 files, 1390 string literals |
| canonical JSON source | ~5.6 MB (66 files) |
| redscript compile | one FULL game restart |

### 5.2 UI strings that must also be localized (not just scripture)
About page, "Books" index header, chapter/verse labels, "Exalted Terminal 77"
title, browser `shortName`, install/readme text. Small, per language.

### 5.3 Text layout per script
Latin/Cyrillic wrap on spaces; **CJK/Thai wrap on character boundaries**
(no spaces) — the paging/line-wrap code in `Site.reds` needs a per-language
break rule. Arabic/Hebrew need RTL base direction + shaping. Currently the
canvas paging is space-based; this is a real code change, not data.

---

## 5.4 Hebrew route (user approved: attempt with a custom font)

Research conclusion: **`.inkatlas` is the wrong tool.** Per the Redmodding wiki,
ink atlases slice *sprite* textures by percentage for icons/avatars — not glyphs.
Text uses `.inkfontfamily` + backing font textures.

The proven community route for a script the game lacks is **font RESOURCE
replacement**: Nexus mod **10153 "Alternate Fonts"** ships fonts as `.archive`
files you drop into `archive/pc/mod` (with published docs on replacing a font in
CP2077). There is **no known mod that adds Hebrew** to the game, so this is
unproven territory — flagging it honestly.

Hebrew plan:
1. Font: **Noto Serif Hebrew** (SIL Open Font License 1.1 — redistributable,
   ships consonants + niqqud, broad Latin/Greek coverage in the same family so
   one family can serve the whole page). OFL text must ship in `CREDITS`.
2. Package as a font-replacement `.archive` in `archive/pc/mod` + an
   `.inkfontfamily` our site can name; **do not** replace the game's core UI font
   globally — that would change the player's whole game. Target only the family
   EXALTED uses.
3. Point `Site.reds` at that family for `he`.
4. **Right-to-left is the real risk.** The engine evidently does bidi + shaping
   (Arabic is an official language), but that is inference, not proof. If ink
   does not reverse base direction, Hebrew renders backwards. Test plan: one
   chapter of Genesis/Psalms, checked on screen, not assumed.
5. Fallback if shaping fails: **pre-reverse** Hebrew strings in the converter
   (visual order) — ugly but shippable, and it keeps the Bible readable.
6. Niqqud (vowel points) may render as misplaced marks; if so, offer a
   consonants-only variant of the text (still scripture, still complete).

---

## 6. Decisions (RESOLVED — user, Oct 4)

1. **Portuguese = pre-1898 Almeida (João Ferreira de Almeida), public domain.**
   Protestant, machine-readable (`por-almeida.usfx.xml`, seven1m/open-bibles),
   shippable. Older revision — accepted knowingly. **ACF and ARC stay excluded
   from every EXALTED build and from distribution.**
   Local `Portuguese-ACF.zip` / `Portuguese-ARC.zip` are still PRESERVED on disk
   (Bible rule) — preservation and distribution approval are two different
   things; they are never shipped.
2. **Hebrew = attempt with a custom font** (§5.4). Unproven in CP2077; pre-reversed
   fallback keeps it shippable.
3. **Packaging = BOTH** per-language packs and one multi-language pack (§5).
4. Still open (non-blocking, defaults proposed):
   - language build order: **P0 Spanish** (validates the pipeline against text we
     already hold) -> P1 French/German/Italian/Dutch/Polish/Czech/Hungarian ->
     P2 Russian/Japanese/Chinese/Korean/Arabic/Thai/Portuguese -> P3 Hebrew.
   - Crosswire footnote apparatus (`\s`/`\f`): **keep** (KJV parity) for English;
     other languages get their own source's apparatus only if public domain.
   - Turkish / Thai / Ukrainian versions: unresolved, research before build.

---

## 7. Definition of done per language (release checklist)

- [ ] Source identified, accepted by user (C4), license verified (C3), sha256 logged.
- [ ] Converted JSON: 66 books, verse counts validated, 0 silent drops.
- [ ] Cleanup parity test (Lua↔Python over every chapter, 0 mismatches).
- [ ] Generated `.reds` compiles clean; `check_bad` passes (0 artifacts).
- [ ] Localized book names + UI strings.
- [ ] **In-game render test** in that language (glyphs, wrapping, RTL where relevant).
- [ ] Version bumped, zip + `.sha256`, install/readme localized,
      `docs/CREDITS.md` licensing section, staging + ToolBox mirror.
- [ ] Bible copy of the source archived to the Bible locations (C5).

Phases: **P0** docs + Spanish pilot (per-language pack) · **P1** Latin-script set
· **P2** script work (Cyrillic/CJK/Arabic/Thai/Portuguese) · **P3** Hebrew font ·
**P4** `.archive` text backend + multi-language pack.

**Next concrete action: implement P0 (Spanish RV1909 pilot)** — it proves
`convert_usfm.py` -> JSON -> `gen-exalted-reds.py` -> redscript -> in-game render
end to end using only text already on disk, before any new source is acquired.
**Implementation awaits explicit user go-ahead.**
---

## 8. P0 Spanish pilot — SHIPPED (Oct 4)

First per-language build is complete and packaged.

- **Artifact**: `dist/EXALTED_Terminal_77-Browser-es-0.1.2.zip`
  (sha256 `d108256cae1151e3dd60b8b08429128668ce4ddb1dbf5e1b3548be2ce1e29acf`),
  mirrored to the Nexus staging folder and the ToolBox drive, all three
  byte-identical.
- **Content**: 66 books / 1189 chapters / **31,102 verses**, 0 red-letter, 0
  empty verses, 0 USFM pilcrows, 0 backslashes, no English leakage.
- **Authority**: the printed RV1909 PDF. Full provenance, source hashes,
  orthographic version fingerprint and both structural adjudications are in
  **`docs/RV1909-SOURCE.md`**.
- **Full details of the two decisions**: 2 Crónicas 16 → 14 verses (PDF's 15th
  folded into v14 after cross-referencing six English traditions plus an
  independent RV1909), and 1 Crónicas 21 → 30 verses (confirmed against
  Wikisource RV1909; the repo's earlier "v30 is a 2 Samuel bleed" note was
  wrong and has been corrected).
- **Wording**: PDF text ships unmodified. 1,454 flagged readings are attached as
  `scripts/rv1909/es-variants.tsv` for a later review pass.
- **Tooling added**: `scripts/rv1909/{rv1909_from_pdf,build_es_from_pdf,
  reconstruct_digital_es,realign_and_variants}.py`. `convert_usfm.py` and
  `package.sh` were extended (ASCII slugs, `EXALTED_SITE_SRC` /
  `EXALTED_LANG_TAG` / `EXALTED_SKIP_CET`) so a language can be packaged
  without touching the shipped English tree.
- **Regression**: the shipped English tree and canonical KJV still regenerate
  byte-identical; all three English zips still build.

Still open for Spanish: wording-defect review, a Spanish CET surface, English
`Site.reds` chrome, and an in-game render test (glyph coverage for the accent
set under Rajdhani).

**Next**: an in-game render test of the Spanish Browser zip, then Portuguese
(pre-1898 Almeida, already source-approved) as the second per-language pack.
