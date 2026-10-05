# EXALTED Terminal 77 — Restart Plan (2026-10-05)

Rebuild the mod from clean `e0287ab` using every measurement made since the
Bible-mod attempt began. Offline-only. Public-domain text only.

**Rule that governs everything below: raw Bible files are read-only and are
never deleted, moved, overwritten or re-encoded.** Cleanup happens only at
render time.

---

## Decisions locked (user, 2026-10-05)

| Question | Call |
|---|---|
| Offline scope | Strip URLs from shipped files **and** repo-wide; drop publishing artifacts; retire Nexus staging |
| Packaging | Per-language packs **first**, then the unified multi pack |
| Fonts | Route A per-language `inkfontfamily` map, now |
| Hebrew | 39-book Tanakh, clearly labelled; download WLC/UXLC |
| Surfaces | **Both** — browser (redscript) and CET terminal (Lua) |
| GitHub repos | User authenticates; agent stays offline and never stores a token |

---

## Standing constraints

- **C1** Bible sources immutable. Converters read, never write, the originals.
- **C2** No Catholic-source text, ever, by lineage rather than by name.
- **C3** Only public-domain text ships.
- **C4** Edition attested from **in-file** metadata, never inferred from a
  filename. This gate caught 6 of 19 wrong attributions.
- **C5** A shipped language's source is archived to the Bible locations.
- **C6** No history rewrite; every artifact gets a `.sha256`.

---

## Phase 0 — Offline baseline (no network, no game)

1. **URL sweep.** Remove `http(s)://` from `cet/EXALTED/CREDITS.txt` (2 GitHub
   URLs; keep project names and MIT notices) and repo-wide including `docs/`.
   Provenance citations become plain text (`Nexus mod 10153`,
   `NativeDB inkTextWidget`) so the evidence survives without a link.
2. **Retire publishing artifacts to a hold folder, never delete:**
   `docs/nexus-description.bbcode.txt` and
   `scripts/rv1909/reconstruct_digital_es.py` →
   `dist/_held-not-shippable/publishing/`. Keep `docs/RV1909-SOURCE.md`; the
   script it cites is an audit witness (held, never run in a build).
3. **Retire the Nexus staging dir** `~/installer-usb/nexus-upload/EXALTED-Terminal-77/`
   and the ToolBox release mirror → `~/installer-usb/_retired-offline/`. No
   uploadable artifact then sits in a staging path.
4. **Add an offline gate** to `package.sh`, beside the existing slug gate,
   refusing to build when the staged tree contains URLs or a
   network API. Runs on every build so this cannot regress.
5. Correct the stale HTML-library text in `~/Projects-Pending.txt` item 18.

## Phase 1 — English in-game gate

Nothing ships until the base surface has been seen on screen. Nothing in
EXALTED has ever rendered.

Bind `EXALTED.OPEN_EXALTED_TERMINAL` (currently `0`) in
`bin/x64/plugins/cyber_engine_tweaks/bindings.json`, launch via `gt77`, then:
terminal opens; home page readable; Genesis ch1 renders, wraps, red-letters;
zero EXALTED errors in the Heroic log at
`…/logs/games/gKHon7YYyofMsKLnz6tzhd_sideload/launch.log`.
This also settles Spanish accent coverage under Raj, currently assumed.

## Phase 2 — Individual languages first

Order: **es → cze → deu → pol → en last**, so the shipped default is
re-verified in its final form. Each language is gated on its own in-game render
before the next begins.

Per language: `scripts/build_lang.sh <lang>` (regenerates from that language's
own `build-report.json`, `--expect-*` as hard assertions) → `package.sh` slug
gate → install → verify on screen.

Slugs stay ASCII and equal the canonical KJV short, so `/b/<short>` resolves in
every language. Spanish ships its 1,454 flagged readings **as-is** with the
ledger attached: fixing inherited-tradition readings makes a build diverge from
its own tradition.

Then the multi pack: `stage_lang_trees.sh` → `langify.py` → one MultiLang zip.
410 modules, 6,950 literals, 21.5 MB — comfortably inside redscript, so the
archive backend stays deferred.

## Phase 3 — `Site.reds` rewrite

Two bugs already found must not regress:

- **Runtime stats line.** `s"66 Books / 1189 Chapters / 31102 Verses"` is
  hardcoded and wrong for 3 of 6: cze 31,172, deu 31,171, dut 31,079. Build it
  from `ExaltedLangVerseTotal(l)` at runtime.
- **Red-letter gating.** Only English has 2,028 red verses. Gate the legend on
  `ExaltedLangRedTotal(l) > 0` or five languages claim letters they lack.

Also in this phase:

- **Font map (Route A).** Replace the hardcoded `raj` at `Site.reds:175` with a
  per-language `SetFontFamily` lookup: Cyrillic → `foreign\russian\raj_rus`,
  Hangul → `foreign\korean\nanum_square`, Han → `foreign\chinese\jing_xi_heig`,
  Thai → `foreign\thai\th_sarabun_new`, Arabic → `foreign\arabic\ara_es_nawar`.
  No font assets shipped; no global UI font replacement.
- **Wrap rule.** Latin/Cyrillic wrap on spaces; CJK/Thai break on character
  boundaries. Per-language rule, not the current space-only pager.
- **Persistence + `/lang` route.** Language state in `RebuildStorage`, picker
  page, header/footer link. Slugs resolve per selected language.
- **Guard:** no `case <n>: if ` anywhere in the tree. `langify.py` emitted that
  once and it is invalid redscript.

## Phase 4 — CET terminal, all languages

`cache.lua` reads `data/kjv/*.json` and is English-only. Per language: its own
`data/<lang>/*.json` tree, `cache.lua` generalized over a language id, and a
Lua↔Python cleanup-parity test — the strip logic (pilcrow, dangling colon,
`+ N.N` margin apparatus) is duplicated by design and must stay provably
identical or the two surfaces drift. `terminal.lua` chrome is hardcoded
English (`"VERSION KJV"`, `"DATA fully local KJV…"`); localize it from
`translations/ui.json`.

## Phase 5 — Hebrew as a labelled 39-book Tanakh

Source: **Westminster Leningrad Codex** or the **tanach.us Unicode/XML
Leningrad Codex** — both explicitly public domain, both machine-readable, so no
transcription is needed. Download to `~/bible-sources/raw/`, log the sha256.

Three facts kept straight:

1. **39 books.** No Hebrew-language New Testament exists. The picker entry and
   About page must not claim 66 books.
2. **`Hebrew.zip` cannot substitute.** It *is* a complete 66-book Hebrew Bible
   by title (בראשית → חזוֹן יוֹחָנָן, Matthew/Mark/Revelation present) but
   its text layer is degenerate: every verse slot in Genesis holds Genesis 1:1,
   1,495 times; Exodus verse 1, 1,205 times. The generating toolchain wrote one
   glyph run per verse. No tesseract on this machine, so no OCR fallback. It
   stays untouched on disk.
3. **The font is the real project.** No shipped Hebrew `.inkfontfamily`
   exists. Route B: Noto Serif Hebrew (SIL OFL) as an `.inkfontfamily` resource
   used **only** by EXALTED, never replacing the game's core UI font.
   `.inkatlas` is the wrong tool — it slices sprites, not glyphs. No known
   CP2077 mod adds Hebrew, so this is unproven; RTL shaping may need a
   pre-reversed fallback.

Does not gate the Latin six.

---

## Repo state (read-only inventory, 2026-10-05)

| Local | Remote | History | Dirty |
|---|---|---|---|
| `gigasort` | `GigaSort---XBaz` | own, 65 files | 4 |
| `Games` | `GigaSort---XBaz` | **unrelated**, 808 files | 757 |
| `gigaorganize` | `gigaorganize` | own | 5 |
| `GigaBook-configs` | `GigaBook-configs` | own | 7 |
| `cyberpunk-exalted` | none | own | 0 |
| `giganet` | none | own | 0 |

`~/Games` and `~/gigasort` share the remote `GigaSort---XBaz` but have **no
shared history** — different root commits, neither resolves the other's objects.
A push from `~/Games` would try to push an unrelated 808-file history onto that
public remote. This is the real repo defect, and it is invisible until someone
pushes. Unresolved: `~/Games` has no correct remote yet.

`cyberpunk-exalted` was public on GitHub through `2c27df4`; the local repo has no
remote. GitHub access requires the user to authenticate; the agent never stores
a token.

---

## Closing acts before any of this is called done

1. **Integrity** — `compileall`, `ruff --select F,B,E9`, converter `--selftest`
   14/14, the new offline gate, fresh-venv install of the built artifact.
2. **Bugs** — exercise each changed path; re-run the test it was meant to satisfy.
3. **Dead code** — no unused imports, no `pass` branches, and ensure no code tries to read/execute the held `reconstruct_digital_es.py` (references exist only in prose/docs pointing to its hold location).
4. **Web cross-reference** — confirm the font-family paths and the WLC/UXLC
   licensing statements still hold, so a later agent does not repeat a stale
   assumption.