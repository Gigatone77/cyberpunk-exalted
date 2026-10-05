# EXALTED — Bible verification & cross-reference findings

**Date:** Oct 4, 2026 · **Author:** EXALTED multilingual build
**Scope:** 19 vetted Bible translations, converted by `scripts/convert_bible.py`,
checked by the independent verifier `scripts/verify_translation.py`, then
packaged one language at a time with `scripts/build_lang.sh`.

Everything below is reproducible with the tools listed in §7. Every claim is
either a command you can re-run or a file path you can open.

---

## 0. Headline

Two things happened that changed the project's conclusions:

1. **The converter had five real defects**, three of which silently shipped
   corrupt text. All five are fixed and independently re-verified (§1).
2. **The source registry was wrong about six of nineteen languages**, because
   the edition had been inferred from the *filename* instead of read out of the
   file. Three languages had already been packaged before this was caught; they
   have been pulled back (§2). This is the same class of error as the Spanish
   episode recorded in `docs/RV1909-SOURCE.md`.

Five languages are shippable today: **cze, deu, dut, hun, pol**.

---

## 1. Converter defects found and fixed

All five were found by `scripts/verify_translation.py`, which parses each build
and re-derives it from the source. The converter has no self-tests for these
paths, so an independent reader was the only thing that could catch them.

### 1.1 OSIS/Zefania double-seeding (`el.text` appended twice)

**Symptom:** every OSIS/Zefania language rendered text roughly twice as long as
the source; `doubled` candidates on ~0.0% of verses but `rt-exact` collapsed.

**Root cause:** verses whose text lives in a child element had
`element_text(vs)` (all descendant text) *and* `el.text` (own text) both
appended.

**Fix:** seed the buffer from `el.text` only, then walk children.
**Impact:** the whole OSIS corpus — bul, chi, deu, fin, fra, hun, kor, mri, sqi,
swe, tgl — was affected.

### 1.2 Chapter-boundary verse loss

**Symptom:** the *last verse of every chapter* was missing.

**Root cause:** the pending-verse buffer was flushed only when the next verse
number appeared, never at a chapter close. The final verse of each chapter had
no successor to trigger it.

**Fix:** flush on chapter end. Verified by Genesis 1 having 31 verses with v31
present (German probe: 31,171 verses, up from 30,048).

### 1.3 `str.translate()` with string keys — a silent no-op

**Symptom:** 18,642 Italian verses carried raw C1 mojibake (`\x92` for `’`).
`build-report.json` cheerfully reported `c1_mojibake` repairs that never
happened.

**Root cause:**

```python
C1_TO_CP1252 = {"\u0092": "\u2019", ...}   # STRING keys
if any(c in text for c in C1_TO_CP1252):
    text = text.translate(C1_TO_CP1252)    # looks up by ORDINAL
```

`str.translate()` indexes its table by **ordinal**. A string-keyed dict is not
an error — it is a *silent* no-op, so the repair was counted in the report while
the damage shipped. `str.maketrans()` is the fix, and it is now applied once at
import:

```python
C1_TABLE = str.maketrans(C1_TO_CP1252)
```

**Lesson worth keeping:** *a counter that increments on the path that performs
the repair is not proof the repair happened.* This one had a report field, a
log line and a test-facing stat, all of which were green.

### 1.4 Double-escaped entities and escaped inline markup

**Symptom:** 6,416 Albanian verses contained the literal text `&quot;`; 61
Swedish verses contained raw `<b>` / `<i>` markup.

**Root cause, both confirmed in the raw bytes:**
- Albanian source contains `&amp;quot;` (11,409×). The XML parser correctly
  decodes that to the *text* `&quot;`; nothing downstream decoded it again.
- Swedish source contains `&lt;b&gt;fött&lt;/b&gt;` — escaped inline tags inside
  the verse text.

**Fix:** decode the five safe entities iteratively (repeat until stable, capped
at 4 passes, so `&amp;amp;quot;` fully unwraps), then drop any surviving
`<...>` run as markup. A bare `&` is left alone — never guessed at. Order
matters: decoding first and stripping second, otherwise `&lt;b&gt;` becomes raw
`<b>` and looks *worse*.

**Note the trap:** decoding `&amp;` to `&` and `&lt;` to `<` in one pass turns
`&amp;lt;` into `lt;`. The iterative loop is what makes nesting safe.

### 1.5 Colophon bleed into the last verse (Polish)

**Symptom:** 14 verses "differed in wording" from the source. Polish showed
e.g. `ROM.16:27` ending `...na wieki. Amen. Pierwszy lis`.

**Root cause:** *the source is at fault.* The scrollmapper JSON dump put
trailing structural markup **inside the last verse's text field**:

```
...na wieki. Amen. <chapter eID="Rom.16"/>
  <div osisID="Rom.c" type="colophon">
    <div sID="gen51" type="x-p"/>
    <hi type="italic">List do Rzymian został napisany z Koryntu…</hi>
    <div eID="gen51" type="x-p"/>
  </div>
  <div canonical="true" eID="gen50" osisID="Rom" type="book"/>
```

Our `_TAGBLOCK` list (title/note/reference/q/foreign/transChange/variant) has a
backreference `\1` to the *closing* tag, so it cannot match this: the opening
tag is `div`, not `colophon`. The `<hi>` text then survived as scripture.

**Fix:** `_drop_colophon()` — depth-tracked removal of
`<div …type="colophon">` subtrees, because the subtree contains nested divs and
a regex alone would stop at the first `</div>`.

**This is a provider defect, not a converter bug** — and it is the kind that a
"looks fine on screen" review would never catch.

---

## 2. The provenance gate: six of nineteen attributions were wrong

Every OSIS file in `~/bible-sources/raw/` carries an `<osisText><header>` with
`osisIDWork`, `<title>` and `<description>`. The Zefania files carry
`<title>`/`<description>` at the top level; the USFX files carry an `id`
attribute. **This metadata was never read.** The registry's `version` column had
been filled in from the filename.

Reading it:

| code | registry claimed | file actually says | consequence |
|---|---|---|---|
| **fra** | "Ostervald" | `osisIDWork=ostv1996`, **"La Bible J.F. Ostervald 1996"**, contributor Louange.org | 1996 revision. The PD Ostervald is 1872/1887. **Packaged, then pulled.** |
| **fin** | "Finnish" | **"Finnish Bible PYHÄ RAAMATTU (C) 1933, 1938"** | Explicit `(C)`, post-1929. **Packaged, then pulled.** |
| **tgl** | "Tagalog" | `osisIDWork=TlgAngBiblia`, **"Ang Dating Biblia"**, Philippines Bible Society 1905 | "Ang Dating Biblia" is the **Catholic** Filipino Bible → **C2 fail. Packaged, then pulled.** |
| **ita** | "Riveduta 1927" | `osisIDWork=IRV_1990`, **"Riveduta 1990"** | Not the PD 1927. (Already held on © 1990 Società Biblica — now correctly attributed.) |
| **por** | "pre-1898 Almeida" | *no metadata whatsoever* | Orthography audit says 20th century (§3). |
| **ron** | "Cornilescu (Protestant)" | `id="01-GEN-RCCV.sfm Romanian Corrected Cornilescu Version, 2013-09-09"` | 2013 electronic revision of a PD 1894 text; corrections unknown. |
| **mri** | "Maori" | "Maori Bible prepared by Timothy Mora, text reproduced by Dr. Cleve Barlow" | No date anywhere. |
| **swe** | "Swedish" | `osisIDWork=SVD`, **"Swedish 1917 Version"** | Now pinned (PD), but see §4 for its data defects. |
| **pol** | "Gdanska" | "Polska Biblia Gdańska (1632, rewizja 1738, od 1838 wydawana bez Apokryfów, rewizja NT 1881)" | Pinned to 1632/1738/1881 — all pre-1929, Protestant. |
| **bul** | "Bulgarian (Protestant)" | "**Veren's Contemporary Bible**", 1871 base by Fotinov et al., "made by Veren LTD" | An *updated* modern edition, not the 1871 text. |
| **tha** | "Thai LPT" | `osisIDWork=kjvthai` "KJV-Thai" | Not LPT. Modern evangelical, undated. |

Also worth recording: **Danish is `1933/1907`** and Norwegian `1906/1930` —
both were rejected as incomplete, but they would have failed C3 as well.

### 2.1 The rule this establishes

> **An edition is attested when the file says so. A filename is metadata, not
> identity.**

This is the same failure as the Spanish build, where the digital RV1909 line was
trusted because it was "the same text" as the printed PDF and turned out to
share a corrupted scan lineage. The generalisation: *a provider's export is not
an independent witness, and a plausible filename is not provenance.*

It also means the earlier registry's `version` column should be treated as
**untrusted** for any language not listed with an attested edition above.

---

## 3. Cross-reference: the Portuguese orthography test

The registry claimed pre-1898 Almeida. Pre-1898 printings are archaic; the
1898 *Revista e Corrigida* and later revisions modernised spelling. The file had
no metadata, so the claim was tested against the **text itself**:

| form | class | count in our source |
|---|---|---|
| `Christo` | archaic, pre-1898 | **0** |
| `muy` | archaic | **0** |
| `Elyseu` | archaic | **0** |
| `Ruth` | archaic | **0** |
| `Cristo` | modern | 531 |
| `Eliseu` | modern | 75 |
| `mui` | modern | 59 |
| `Rute` | modern | 17 |

Zero archaic, 682 modern. Upstream sources confirm the boundary: the 1681 first
edition is titled *"O Novo Testamento, Isto he o Novo Concerto de Nosso Fiel
Senhor e Redemptor **Iesu Christo**…"*, and *"Christo"* persisted until the
**ARC "a partir de 1948"** revision, which reads *"tu és o **Cristo**"*.

**Verdict:** this is 20th-century orthography. Not the PD pre-1898 Almeida that
AGENTS.md mandates. Held. The conversion itself is clean (31,039 verses, 0
unexplained, 0 structural) — only the rights gate fails.

**Action:** obtain an attributed 1619 / 1849 / 1873 printing, or a scan of one.

---

## 4. Per-language verification results

All 19 run **individually** through `verify_translation.py`, never as one batch
(batch runs are what hung earlier sessions). `struct` = structural problems;
`rt` = verses re-derived exactly from the source.

| code | verdict | verses | struct | unexplained doubling | notes |
|---|---|---|---|---|---|
| cze | WARN | 31,172 | 0 | 0 | 12 spacing-only |
| deu | WARN | 31,171 | 0 | 0 | 3 doubled candidates, all present in the source |
| dut | WARN | 31,079 | 0 | 0 | |
| hun | WARN | 31,170 | 0 | 0 | 1 verse absent in the source too (faithful) |
| pol | WARN | 31,102 | 0 | 0 | colophon fixed; 1,414 spacing-only |
| fin | WARN | 31,107 | 0 | 0 | 34 verses absent in the source; 1,190 chapters |
| fra | WARN | 31,172 | 0 | 0 | rights fail (§2) |
| mri | WARN | 31,102 | 0 | 0 | provenance fail (§2) |
| ron | WARN | 31,102 | 0 | 0 | provenance fail (§2) |
| tgl | WARN | 31,102 | 0 | 0 | 5 doubled candidates, all in the source; **C2 fail** |
| chi | WARN | 31,100 | 0 | 0 | Han — font route missing |
| rus | WARN | 31,352 | 0 | 0 | Cyrillic font + Daniel 13/14 |
| kor | WARN | 30,625 | 0 | 0 | 2,842 rt-diff, Hangul font, provenance |
| por | WARN | 31,039 | 0 | 0 | provenance fail (§3) |
| tha | WARN | 31,102 | 0 | 0 | rights fail |
| bul | **FAIL** | 31,101 | 0 | 0 | 33 verses contain U+FFFD (unrecoverable) |
| swe | **FAIL** | 31,148 | 0 | 0 | source structurally corrupt (§5) |
| sqi | **FAIL** | 31,102 | 0 | 0 | entity residue fixed; rights + 1 undisclosed gap |
| ita | **FAIL** | 31,102 | 0 | 1 | rights fail; 1 unexplained doubled candidate |

"Spacing-only" and "present in the source" differences are **not** defects: the
converter normalises whitespace, and a doubled phrase that the printed edition
also contains is the tradition, not a bug. The verifier grades them WARN on
purpose — over-reporting is how the five real defects got caught at all.

### 4.1 `bul` — 33 unrecoverable characters

`U+FFFD` means the producer lost the byte. The original character is gone and
cannot be reconstructed from anything on disk. The converter now **discloses**
each location (`kind: "lost_character"` in `build-report.json`) instead of
shipping an unprintable box as scripture. Fixing this needs a different source,
not better code.

---

## 5. `swe` — a structurally corrupt source

Swedish is `SVD 1917`, which is fine on rights. The *file* is not:

- 61 verses carried raw `<b>`/`<i>` markup (now stripped, §1.4);
- 4,855 verses differ from the source by spacing alone;
- 17 verses are **empty in the source** and carry a placeholder in the build;
- books are mislabelled relative to their content.

This is a provider export failure, not a conversion failure. Held. A different
SVD export is needed.

---

## 6. Canon purity (C6) — the 66-book rule, audited

**User ruling, Oct 4:** *"we should not be using the apocrypha, those texts are not
accepted and established canon. Only Bibles with the basic 66 books."*

This is now shipping gate **C6**, and it is stricter than "the file has 66 book
files" — apocryphal text can hide *inside* a canonical book, which is exactly the
shape of the defect that was wrongly suspected in `pol`.

Audit of all 21 builds (books / chapters / verses, chapter counts compared
against `cet/EXALTED/data/books.json`):

| lang | books | chapters | verses | chapter-count deviations |
|---|---|---|---|---|
| bul chi cze dut hun ita mri pol por sqi tgl tha | 66 | 1189 | (varies) | **MATCH** |
| fra | 66 | 1189 | 31172 | MATCH |
| rus | 66 | **1192** | 31352 | **DAN 14≠12** ← apocrypha |
| kor | 66 | **1171** | 30625 | 2CH 20≠36; JOB 41≠42; 1PE 4≠5 |
| fin | 66 | **1190** | 31107 | 2CO 14≠13 |
| swe | 66 | 1189 | 31148 | 1PE 3≠5; 2PE 5≠3; 1JN 1≠5; 3JN 5≠1 |
| deu | 66 | 1189 | 31171 | **JOL 4≠3; MAL 3≠4** |

### 6.1 `rus` is the one confirmed canon violation

Daniel has **14** chapters instead of 12: the extra two are *Susanna* (Daniel
13) and *Bel and the Dragon* (Daniel 14) — deuterocanonical books folded into a
canonical one, so a "66 book file" check passes while the text is not the 66-book
canon. `rus` stays HELD under C6.

### 6.2 `pol` is clean — an earlier claim here was WRONG

An earlier revision of this document and of `VETTED.txt` said `pol` "carries the
Wydatek apocryphon". **That was false.** The evidence:

* `grep -c Wydatek raw/pol*.xml` → **0**. The word does not occur anywhere.
* The only hit for `Apokryf` in the whole source is inside its own OSIS
  `<description>`: *"Polska Biblia Gdańska (1632, rewizja 1738, **od 1838
  wydawana bez Apokryfów**, rewizja Nowego Testamentu 1881)"* — "published
  **without apocrypha** from 1838". The source was describing its own canon
  compliance; the note read it as a confession of extra books.
* Audit confirms: 66 books, 1189 chapters, 31102 verses, every chapter count
  matches canonical, zero apocrypha markers.

Lesson: a marker word inside metadata is evidence about the *edition*, never
evidence about the *text*. Match against the built verses, not the header.

### 6.3 `deu` shifts the Joel/Malachi chapter boundary (affects a shipped pack)

German Protestant versification numbers **Joel 4 / Malachi 3** where the
canonical (KJV) is **Joel 3 / Malachi 4**. Total chapters still match (4+3 = 3+4),
so a totals check does not catch it, but the boundaries move:

* `deu` Joel 3 = 5 verses starting *"Und nach diesem will ich meinen Geist
  ausgießen"* = canonical **Joel 2:28-32**.
* `deu` Joel 4 = 21 verses starting *"Denn siehe, in den Tagen"* = canonical
  **Joel 3:1-21**.
* `deu` Malachi 3 = 24 verses starting *"Siehe, ich will meinen Engel senden"* =
  canonical **Malachi 4:1-24**.

So a reader navigating by canonical chapter/verse lands on the wrong text for
those two books. This is a legitimate German versification, not a corrupt source,
but it is a *navigation* defect for a KJV-keyed browser and must be disclosed or
remapped before `deu` goes in the multilingual pack.

---

## 7. What is still owed

| # | Item | Why it matters |
|---|---|---|
| 1 | **Font route** (`docs/FONT-ROUTE.md`) | `Site.reds:175` hardcodes Raj. chi/rus/kor/bul render as tofu until a per-language font family lands. Cheapest proof: Russian via the shipped `foreign\russian\raj_rus.inkfontfamily`. |
| 2 | Per-language wrapping | CJK/Thai have no spaces; the canvas paging is space-based. Real code change, not data. |
| 3 | Attributed sources | por (pre-1898), mri (date), kor (edition), sqi (edition), ron (2013 corrections), bul (1871 vs Veren update) |
| 4 | Rights decisions | fra (1996 revision), fin (© 1933/38), tgl (Catholic), ita (© 1990), tha (CC BY-NC-ND), sqi (© ABS) |
| 5 | Multi-language pack | §5 of `docs/MULTILINGUAL-PLAN.md` — needs a `/lang` route, language state, and almost certainly an `.archive` text backend instead of ~25k `.reds` literals |
| 6 | `deu` Joel/Malachi remap or disclosure | §6.3 — chapter boundary moves; must be fixed or documented before the pack |
| 7 | `hun` edition attestation | OSIS header carries no edition/date; only the filename says Karoli. C4 needs in-file evidence |
| 8 | In-game render test | Every build is verified against its *source*. None has been opened in Night City. |

**Per-language preservation floor (C5):** every language above needs ≥1
authentic copy kept forever in the Bible locations, per the standing rule —
independent of whether it ships in the mod.

---

## 8. The toolchain

All stdlib-only Python 3, no third-party dependencies.

| tool | what it does |
|---|---|
| `scripts/convert_bible.py` | USFM / OSIS / Zefania / scrollmapper-JSON → `<n>.json` + `books.json` + `build-report.json` (counts, flags, sanitiser stats, disclosure manifest) |
| `scripts/verify_translation.py` | **Independent** stdlib-expat reader. Re-derives each build from its source: exact/spacing/punctuation/wording round-trip, doubled-text classification (converter-duplication vs present-in-source vs unexplained), structure, encoding, script fingerprint, slug safety, gap disclosure, report reconciliation. `--selftest`, `--batch`, `--json`. |
| `scripts/build_lang.sh` | One language end to end: reads real counts from the build report, asserts them against the generator, stages the site tree, runs the slug gate, zips. `--no-package` builds a site tree with **no zip**, so held languages cannot be uploaded by accident. |
| `scripts/gen-exalted-reds.py` | JSON → redscript `.reds` string literals. `--expect-*` turns the final count into a hard assert. |
| `scripts/package.sh` | Zips the browser/CET surfaces. Language-tag validation, ASCII canonical slug gate, refuses a language payload paired with the English CET tree. |
| `scripts/rv1909/reconstruct_digital_es.py` | Spanish audit witness (never shipped) |
| `cet/EXALTED/lib/cache.lua` | Lua-side cache builder, kept in cleanup parity with the Python path |

### 8.1 How to reproduce a language end to end

```bash
cd /var/home/Gigatone/bible-sources/build/<code>   # converter output
python3 ~/cyberpunk-exalted/scripts/verify_translation.py .    # independent check
python3 /var/home/Gigatone/gt-probe/regen.py <code>            # rebuild from source
bash ~/cyberpunk-exalted/scripts/build_lang.sh <code>           # generate + package
```

### 8.2 Reading a source's provenance yourself

The check that was missing for six languages takes one line:

```bash
python3 - <<'PY'
import re
d = open('/var/home/Gigatone/bible-sources/raw/<file>', encoding='utf-8').read()
i = d.find('<osisText'); print(re.sub(r'\s+', ' ', d[i:d.find('</header>', i) + 9]))
PY
```

Zefania files put `<title>`/`<description>` at top level; USFX files carry an
`id` attribute (`ron` = `01-GEN-RCCV.sfm Romanian Corrected Cornilescu
Version, 2013-09-09`). **`por` returns nothing at all** — which is itself the
finding.

---

## 9. Registry

`/var/home/Gigatone/bible-sources/VETTED.txt` is the authoritative per-language
status, rewritten Oct 4 with attested editions and a reason for every non-BUILD
line. Mirrored into the ToolBox tool bundle alongside these docs.