# EXALTED Terminal 77 — Font Rendering Route (Non-Latin Text)

Status: **RESEARCH DOCUMENT** — feasibility assessment for Cyrillic, Hangul, Han (Traditional/Simplified), Thai, Greek, Arabic and Hebrew. Latin is proven (Spanish Browser pack shipped Oct 4).

## 1. Headline answer: can non-Latin render in-game today?

| Script class | In-game today? | Why (evidence) | Failure mode if using Latin-only (Raj) |
|---|---|---|---|
| **Cyrillic** (Russian, Bulgarian, Ukrainian) | **Yes** | Game ships `gameplay\gui\fonts\foreign\russian\raj_rus.inkfontfamily` (Raj Russian). NativeDB/WolvenKit font list confirms it. | **Tofu/glyph fallback failure** — without selecting the Russian font family, Cyrillic glyphs are not covered by `raj` and will render as missing glyphs (boxes/question marks) in inkText. |
| **Greek** | **Unclear/likely partial** | Greek is not listed among the explicit foreign inkfontfamily entries in NativeDB/DoctorPresto lists (Arabic, CJK, Korean, Japanese, Thai, Russian only). Game localizations include some European languages, but a dedicated Greek ink font family is **not evident** from the shipped families. | **Likely tofu** if no Greek font family is selected; may depend on whether some shared Latin font contains Greek glyphs. **UNVERIFIED**. |
| **Hangul (Korean)** | **Yes** | Shipped families: `foreign\korean\kbiz_go.inkfontfamily`, `foreign\korean\nanum_square.inkfontfamily`. | Tofu if hardcoded to Raj. |
| **Han — Simplified Chinese** | **Yes** | `foreign\chinese\jing_xi_heig.inkfontfamily` | Tofu if hardcoded to Raj. |
| **Han — Traditional Chinese** | **Yes** | `foreign\chinese_traditional\ar_fang_xing_run_yuan.inkfontfamily`, `foreign\chinese_traditional\jing_xi_heig_b5.inkfontfamily` | Tofu if hardcoded to Raj. |
| **Japanese (Kanji/Hiragana/Katakana)** | **Yes** | `foreign\japanese\mgenplus.inkfontfamily`, `foreign\japanese\smart_font_ui.inkfontfamily` | Tofu if hardcoded to Raj. |
| **Thai** | **Yes** | `foreign\thai\printable4u.inkfontfamily`, `foreign\thai\th_sarabun_new.inkfontfamily` | Tofu if hardcoded to Raj. |
| **Arabic** (RTL) | **Yes** | `foreign\arabic\ara_es_nawar.inkfontfamily` | Tofu if hardcoded to Raj; RTL + shaping requirements apply. |
| **Hebrew** | **No (shipped fonts lack dedicated family)** | No Hebrew `.inkfontfamily` listed in NativeDB/DoctorPresto font lists. Game has no Hebrew localization. | **Hard tofu / unmappable glyphs**. Requires custom font resource. |

**Key point:** The engine *can* render non-Latin scripts if you select the appropriate ink font family. The blocker is that the browser site currently hardcodes `base\gameplay\gui\fonts\raj\raj.inkfontfamily` (Site.reds:175). That must change per language/script class.

## 2. Evidence cited (what was read)

| Source | Type | What it shows |
|---|---|---|
| [NativeDB — inkTextWidget](https://wiki.redmodding.org/nativedb-documentation/classes/inktextwidget) / [NativeDB wiki copy](https://github.com/CDPR-Modding-Documentation/NativeDB-wiki/blob/main/classes/inktextwidget.md) | Redmodding wiki | `SetFontFamily(fontFamilyPath, opt fontStyle)` and the known relative paths under `base\gameplay\gui\fonts\` including `foreign\russian\raj_rus`, `foreign\korean\*`, `foreign\japanese\*`, `foreign\chinese*\*`, `foreign\thai\*`, `foreign\arabic\*`, and `raj`. Confirms inkText uses `.inkfontfamily`. |
| [DoctorPresto/Cyberpunk-File-Types — inkfontfamily.txt](https://github.com/DoctorPresto/Cyberpunk-File-Types/blob/main/inkfontfamily.txt) | Data list | Canonical list of shipped `.inkfontfamily` files (matches above; **no Hebrew** present). |
| [DoctorPresto/Cyberpunk-File-Types — fnt.txt](https://github.com/DoctorPresto/Cyberpunk-File-Types/blob/main/fnt.txt) | Data list | References `.fnt` (bitmap font) files backing those families. |
| [Redmodding — Change font & language setting (CET)](https://wiki.redmodding.org/cyber-engine-tweaks/console/settings/config-file/change-font-and-font-size) | Guide | CET ImGui font configuration shows `language` options: `Cyrillic`, `ChineseFull`, `ChineseSimplifiedCommon`, `Japanese`, `Korean`, `Thai`, `Vietnamese`. Confirms engine has non-Latin language/font handling. |
| [Redmodding — Importing raw files to REDengine](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators-theory/modding-tools/redmod/importing-raw-files-to-redengine) | Tooling | `.ttf/.otf/.cff` can be imported to `.fnt`/font resources via Redmod (relevant for custom font packaging). |
| [Alternate Fonts (Nexus 10153)](https://www.nexusmods.com/cyberpunk2077/mods/10153) + [Docs](https://www.nexusmods.com/cyberpunk2077/mods/10153?tab=docs) | Nexus mod (community) | Documents **font replacement via `.archive`** and WolvenKit workflow for replacing game font resources. This is the established community route for shipping font changes. |
| [Redmodding — Custom in-game icons / inkatlas](https://wiki.redmodding.org/cyberpunk-2077-modding/modding-guides/custom-icons-and-ui/custom-in-game-icons) | Reference | Clarifies `.inkatlas` is sprite slicing (not glyph atlas for arbitrary text). Confirms `.inkatlas` is the **wrong** mechanism for adding text glyph coverage; use font resources/families. |
| [Project repo (verified)](https://github.com/Gigatone77/cyberpunk-exalted) | Local repo | `Site.reds:175` hardcodes `base\gameplay\gui\fonts\raj\raj.inkfontfamily` (per `docs/BROWSER-SITE.md`). Generator and surfaces unchanged except data. |

## 3. Routes compared (with evidence-based ranking)

| Route | What it does | Feasibility | Effort | Risk | Notes |
|---|---|---|---|---|---|
| **A. Select correct shipped `.inkfontfamily` per language (no new font assets)** | In redscript, set `inkTextWidget.SetFontFamily()` to the game's foreign family for that script (e.g. `foreign/russian/raj_rus/raj_rus.inkfontfamily` for Cyrillic, `foreign/korean/nanum_square/nanum_square.inkfontfamily` for Korean, `foreign/chinese/jing_xi_heig/jing_xi_heig.inkfontfamily` for Simplified Chinese, `foreign/japanese/mgenplus/mgenplus.inkfontfamily` for Japanese, `foreign/thai/th_sarabun_new/th_sarabun_new.inkfontfamily` for Thai, `foreign/arabic/ara_es_nawar/ara_es_nawar.inkfontfamily` for Arabic). | **High** | **Low** | **Low** | This is the correct way for scripts the game already supports. Requires a **per-language font-family map** in `Site.reds` (or detect by language). No asset redistribution. No global font replacement of player's UI. |
| **B. Ship a custom font replacement as `.archive` (replace/override font resource)** | Package a TTF/OTF converted to game font resources and ship as `.archive` (Alternate Fonts mod pattern). Can target a specific family or replace an existing one. To avoid affecting player's whole UI, best to add/override a dedicated family used **only** by EXALTED, not the core UI. | **Medium–High** | **Medium** | **Medium** | Proven community pattern (Nexus 10153). Requires WolvenKit + Redmod font import workflow. Must respect font license (OFL/Apache etc). Hebrew is the only script in scope with **no shipped family**. Global replacement of game fonts affects all UI — avoid unless necessary. |
| **C. Ink atlas (bitmap glyphs)** | Generate an `.inkatlas` with pre-rendered glyphs per character. | **Low–Medium** | **High** | **High** | Wrong tool for text (inkatlas is sprite slicing). CJK alone needs tens of thousands of glyphs; memory, atlas size, maintenance, and dynamic text (search results) are impractical. As per Redmodding docs, this is not the text rendering path. **Not recommended**. |

**Ranking per script class (feasibility × effort × risk):**
- Cyrillic, Korean, Japanese, Chinese (Simplified/Traditional), Thai, Arabic: **Route A > Route B >> Route C**. Route A is sufficient and safe.
- Greek: **Route A uncertain (no explicit shipped family)** — may need Route B if no suitable family exists in game.
- Hebrew: **Route B >> Route C >> A (impossible)**. No shipped family exists; must ship custom font resource. Route A is not an option.

## 4. Font families to use (Route A, per language)

Based on shipped families (NativeDB/DoctorPresto):

| Language(s) | Recommended `.inkfontfamily` (relative to `base\gameplay\gui\fonts\`) | Font style(s) | Notes |
|---|---|---|---|
| **Russian, Bulgarian, Ukrainian** | `foreign\russian\raj_rus\raj_rus.inkfontfamily` | Regular/Bold as available | Raj Russian variant exists (matches Raj Latin style). |
| **Korean (Hangul)** | `foreign\korean\nanum_square\nanum_square.inkfontfamily` or `foreign\korean\kbiz_go\kbiz_go.inkfontfamily` | Regular/Bold | Nanum Square is common UI font; test for readability at in-browser sizes. |
| **Japanese** | `foreign\japanese\mgenplus\mgenplus.inkfontfamily` or `foreign\japanese\smart_font_ui\smart_font_ui.inkfontfamily` | Regular/Bold | MgenPlus is widely used. |
| **Simplified Chinese (chi)** | `foreign\chinese\jing_xi_heig\jing_xi_heig.inkfontfamily` | Regular | Jing Xi Hei G. |
| **Traditional Chinese (CUV)** | `foreign\chinese_traditional\jing_xi_heig_b5\jing_xi_heig_b5.inkfontfamily` or `ar_fang_xing_run_yuan\ar_fang_xing_run_yuan.inkfontfamily` | Regular | Test readability. |
| **Thai (tha)** | `foreign\thai\th_sarabun_new\th_sarabun_new.inkfontfamily` or `foreign\thai\printable4u\printable4u.inkfontfamily` | Regular/Bold | Sarabun New is common. |
| **Arabic (ar)** | `foreign\arabic\ara_es_nawar\ara_es_nawar.inkfontfamily` | Regular/Bold | **RTL + shaping required**. inkText's bidi behavior needs in-game verification. |
| **Greek** | **UNVERIFIED** — no explicit family listed. Test existing Latin families first; if Greek glyphs are missing, consider a custom Greek font family (Route B). | — | Greek is not in the foreign list above. |

## 5. Hebrew (first-class; custom font required)

**Conclusion (from evidence):** No Hebrew `.inkfontfamily` is shipped (NativeDB/DoctorPresto lists confirm). Game has no Hebrew localization. Route A is not possible. **Route B (custom font resource in `.archive`) is required**.

### Recommended approach (Route B)

1. **Font choice:** Use a permissively licensed Hebrew font with good glyph coverage (consonants + niqqud). Example: **Noto Serif Hebrew** (SIL Open Font License 1.1) — covers Hebrew, includes niqqud marks, and is commonly used. **Only reference font names/licenses; do not include font binaries** in repo/docs.
2. **Do not globally replace game UI fonts.** Create/override a **dedicated** `.inkfontfamily` (e.g. `exalted\fonts\hebrew\noto_serif_hebrew.inkfontfamily`) and point EXALTED’s Hebrew site/reader to that family only. This matches Alternate Fonts pattern while minimizing side effects.
3. **Packaging:** Ship as `.archive` containing the converted font resources + the ink font family definition, placed in `archive/pc/mod`. Use WolvenKit/Redmod workflow to import TTF/OTF into game font resources (per Redmodding import docs).
4. **RTL + bidi:** Hebrew is RTL. Arabic is an official game language and uses `ara_es_nawar`, so the engine **likely supports RTL/bidi/shaping** for inkText. However this is **inference**, not proof for arbitrary custom fonts. Test required.
5. **Fallback strategies (pragmatic):**
- If shaping/niqqud renders poorly in practice: **pre-reverse** Hebrew strings at generation time (visual order) — keeps text readable. This is a data-layer trade-off (converter change) but avoids complex shaping issues.
- If niqqud is misaligned: offer a **consonants-only** variant of the text (still scripture). Document in release notes.
6. **Attribution:** Include OFL text in `docs/CREDITS.md` if redistributing the font. Respect all license terms.

**Cost estimate (honest):** Medium effort. Requires font conversion/import, packaging, redscript changes (per-language family selection), and in-game verification. Unproven territory for CP2077 (no known Hebrew mod for game UI text via ink font family in this context).

## 6. What breaks if we do nothing (failure modes)

| Language | With hardcoded Raj only | Concrete failure |
|---|---|---|
| **Russian (rus)** | Glyphs missing | Cyrillic characters render as **tofu boxes / replacement glyphs** (not mojibake from encoding). inkText cannot display Cyrillic if the selected family has no Cyrillic coverage. |
| **Bulgarian (bul)** | Glyphs missing | Same as Russian (Cyrillic). |
| **Korean (kor)** | Glyphs missing | Hangul syllables render as tofu. Jamo composition depends on font. |
| **Traditional Chinese (chi/CUV)** | Glyphs missing | Han characters render as tofu. |
| **Simplified Chinese** | Glyphs missing | Same as Traditional. |
| **Thai (tha)** | Glyphs missing | Thai characters + combining marks render as tofu/misaligned without proper font. |
| **Greek** | **UNVERIFIED** | If no Greek coverage in Raj, tofu. If partially covered (some fonts include basic Greek), may render but not guaranteed. |
| **Hebrew** | **No glyph coverage** | Tofu for all Hebrew characters; RTL unreadable without proper font + direction. |

**Important:** This is glyph coverage failure, not UTF-8 mojibake. Our generated `.reds` string literals are UTF-8; redscript strings carry Unicode. The rendering surface (inkText + selected font family) is what determines glyph availability.

## 7. Staged recommendation (cheapest next proof)

### Current state
- Latin script: **proven** (Spanish Browser pack shipped). The pipeline (JSON → `.reds` → redscript → in-game browser via `NETdir://exalted.terminal`) works.

### Cheapest next language to prove end-to-end
**Russian (rus)** is the cheapest next proof.

**Rationale:**
1. **Route A is sufficient** — game ships `foreign\russian\raj_rus\raj_rus.inkfontfamily`. No font assets to ship or license.
2. **Small script change scope** — only need per-language font-family selection in `Site.reds` (and localized UI strings if desired). No RTL, no tens-of-thousands-of-glyph CJK shaping edge cases compared to Hebrew/Arabic in complexity.
3. **PD source exists** (Synodal 1876, per `MULTILINGUAL-PLAN.md`) and text pipeline is the same (66 books/chapters/verses). Cleanup parity applies.
4. **Clear pass/fail** — if Russian renders correctly with `raj_rus`, Cyrillic is validated. If it renders as tofu with hardcoded Raj, that confirms the font-family selection is the fix.

### Recommended order of proof (staged)

1. **P1a — Russian (Cyrillic, Route A)**: cheapest, proves per-language font family selection works. **This is the next language to prove.**
2. **P1b — Korean / Japanese / Simplified/Traditional Chinese / Thai** (Route A): each validates another script class with shipped families. Thai has combining marks; CJK has no spaces (wrapping already flagged in plan — §5.3 of MULTILINGUAL-PLAN.md notes CJK wrap on character boundaries).
3. **P1c — Arabic** (Route A): validates RTL + shaping with shipped family; higher risk than Cyrillic but still uses existing game fonts.
4. **P2 — Greek** (unknown): test Route A first (does any shipped family cover Greek glyphs?). If not, evaluate Route B with permissively licensed Greek font.
5. **P3 — Hebrew** (Route B): only attempt after P1c validates RTL behavior conceptually; requires custom font resource + possible pre-reversal fallback. Highest effort/risk.

### Immediate implementation change (to enable Route A for all supported scripts)
Modify `Site.reds` to select font family by language (not hardcoded Raj). For the browser surface, detect language from the active site/language context (or pass language when building pages). The current code at line ~175 in `Site.reds` sets Raj unconditionally; this is the single-line blocker for all non-Latin scripts the game already supports.

## 8. UNVERIFIED list (be honest about uncertainty)

| Item | Status | What would settle it |
|---|---|---|
| **Greek glyph coverage** | **UNVERIFIED** | In-game test: load Greek text (e.g. Greek Bible/NT) in the browser with `raj` vs the best candidate family. If Greek renders as tofu with all shipped families, Greek needs Route B. |
| **Arabic RTL + shaping in inkText (custom vs shipped)** | **UNVERIFIED** | In-game test with Arabic (shipped family) — check base direction, ligatures, diacritics positioning. The engine supports Arabic as official locale, so likely OK, but needs empirical confirmation. |
| **Hebrew RTL + niqqud rendering quality** | **UNVERIFIED** | In-game test with a custom `.inkfontfamily` + Noto Serif Hebrew (or equivalent OFL font). Check niqqud alignment, word order. If poor, test pre-reversed visual-order text as fallback. |
| **CJK line wrapping behavior with inkText** | **UNVERIFIED (implementation detail)** | Current reader uses space-based wrapping logic conceptually (per `BROWSER-SITE.md` §5.3 and generated line wrapping at 76 chars). CJK has no spaces; need to verify inkText's wrapping for CJK text and/or adjust paging/break rules per language. The plan already calls this out — requires code change. |
| **Custom font family reference path/name stability** | **UNVERIFIED** | When shipping a custom `.inkfontfamily` via `.archive`, the relative path must be discoverable by inkText. Community examples exist (Alternate Fonts), but we need to confirm our mod-only family path is not overridden by core game UI. Best practice: use a unique path under `exalted\` or mod-specific namespace. |
| **Thai combining marks rendering** | **UNVERIFIED** | In-game test with shipped Thai family (`th_sarabun_new`) — some fonts need proper OpenType shaping for Thai; inkText behavior in CP2077 for complex Thai sequences needs verification. |

## 9. Conclusion (concise)

- **For Cyrillic/Korean/Japanese/Chinese/Thai/Arabic:** Route A (select correct shipped `.inkfontfamily` per language) is feasible, low effort/risk. The blocker is the hardcoded Raj in `Site.reds`. Fix that first.
- **For Greek:** Unknown; test shipped families first.
- **For Hebrew:** Route B required (custom font resource). Treat as P3 after validating RTL with Arabic (Route A) and confirming approach.
- **Cheapest next proof language:** **Russian** (Route A) — validates the per-language font family mechanism with zero font asset redistribution and clear pass/fail.
- **Critical constraint respected:** No Bible data modified (read-only). Font work is feasibility/documentation only as requested; no code changes made in this task.

_This document is based on Redmodding wiki references, NativeDB font family lists, DoctorPresto file-type lists, and the Alternate Fonts mod pattern. All citations above are verifiable._
