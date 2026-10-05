# Spanish RV1909 — source, provenance and decisions

Status: **Spanish Browser pilot SHIPPED** (Oct 4). Artifact:
`dist/EXALTED_Terminal_77-Browser-es-0.1.2.zip`.

## What ships

| | |
|---|---|
| Books / chapters / verses | 66 / 1189 / **31,102** |
| Red-letter verses | 0 (Spanish module carries no red-letter markup) |
| Text authority | the local printed RV1909 PDF (`Documents/20/Bibles/Spanish.zip`) |
| Display names | Spanish (`Génesis`, `2 Crónicas`) |
| URL slugs | ASCII (`Gen`, `2Chr`) — see "Slugs" below |
| Packaging | English `Site.reds` shell + Spanish `data/` payload |

Nothing outside `translations/es/` and the generated `.reds` payload is
touched. The shipped English tree (`internet/EXALTED/`) and the canonical KJV
data regenerate **byte-identical**.

## Source hashes

| File | sha256 |
|---|---|
| `Documents/20/Bibles/Spanish.zip` | `1d8545c59c5c77debce3654f7a4641a79a83bc0db03490af197fccf683b4507d` |
| `Spanish.zip` book 1 PDF | `8c309b12ce1c0da503f8fccbdbb517a84ff9a7e4b818a63929c87d3400c3a7cb` |
| `spaRV1909_usfx.zip` (eBible digital, witness only) | `a2540fae5eee98d50df14ddaa6dbf36450fce1319c7937000705d12285fb5408` |
| `spaRV1909_readaloud.zip` | `fe644a3468d7bd97cdca1c18e61322dd474b46216726ed49e56db1dc517c8b97` |
| BibleAquifer `Spanish-usfm.zip` | `cf73fb8a1b1646e363f4d2a797b5474bbe38c41e5e74757ad53c25fe98cd3e98` |
| Project Gutenberg #5881 NT (cross-check) | `4ad31ff6ec7ac9341c8642166647c92bf5bc5bd5e71085d5bb2098f7210b302b` |
| rebuilt digital witness (66 JSON) | `d44e213d2f98b01bf18f8191a776c1096b9d5cdb1059eb9c6d9f7f6b1f2730f9` |

The PDF carries **no title page, publisher, imprint or licence** — its edition
cannot be proven from the file. See "Version fingerprint" for how it was
identified anyway.

## Version fingerprint (PDF identified without an imprint)

The scanned edition is positively confirmed as **Reina-Valera 1909**, not a
later revision, by orthography:

| Marker | Count | Meaning |
|---|---|---|
| `fué` | 1,733 | pre-1959 orthography; RVR1960 prints `fue` |
| `á` (as preposition) | 18,977 | dropped in RVR1960 |
| `Jehová` | 6,782 | RV1909 house style |
| `vosotros` | 1,652 | RV1909; RVR1960 uses `ustedes` |
| `ustedes` | 0 | confirms it is NOT RVR1960 |

`SEÑOR` (4) and `Palestina` (7) were checked individually and are legitimate
(all-caps superscriptions, Apocalipsis 19:16, and OT place names).

## Structural adjudications

**2 Crónicas 16 → 14 verses (PDF's 15th folded back into v14).**
The PDF splits the chapter after the semicolon in *"…en la ciudad de David; Y
pusiéronlo en una litera…"*. Cross-referenced against KJV, Geneva, ASV, WEB,
BSB and NLT — all read 14 verses, merging 2 Sam 21:18–19 into v14, which is the
standard versification and makes 15 the outlier. The OpenBible-derived Spanish
text at chasten.ai also reads 14 with the semicolon clause *inside* v14, but it
is the **same lineage** as the eBible digital witness (see the lineage finding
below), so it corroborates without being independent. The PDF split is a
printing artifact, not a versification difference. Merging reproduces the
received text **byte-identically**. User decision, Oct 4.

**1 Crónicas 21 → 30 verses (PDF's 31st verse dropped).**
Wikisource's Reina-Valera 1909 ends the chapter at v30, *"Mas David no pudo ir
allá á consultar á Dios, porque estaba espantado á causa de la espada del ángel
de Jehová"* — which is exactly the PDF's v30. So v30 is genuine 1 Crónicas
text, **not** a 2 Samuel 24:19 bleed (an earlier note in this repo claimed the
opposite and was wrong); only v31 is spurious. RVC and both digital sources also
read 30.

Result: 31,102 verses — matching the digital module's count, from a text whose
*numbering* is the PDF's and whose *2 Cr 16* reading is attested by the standard
English versification.

## Wording defects: shipped as-is, ledger attached

The PDF has character-level OCR defects (`tabajo`, `cundo`, `isrelitas`,
`ingnoreis`, `esctrito`, …). They are **not** repaired in the shipped text.
User decision, Oct 4.

Reason repair was not automated: the digital witness is **not** safe as an
automatic corrector — in many disagreements the PDF is the correct reading
(Éxodo 20:21 PDF `obscuridad` vs digital `osbcuridad`; Malaquías 1:13 PDF
`vuesta` is right; Job 32:5 PDF `aquelllos` is the defect, not the digital).
Automated gates also fire on rare-but-valid words (`aceca` = a city,
`costas`, `casos`, `afrento`), so they cannot separate OCR garbage from
archaic Spanish without a lexicon.

The flagged readings ship as reviewable evidence:

| File | Rows | What |
|---|---|---|
| `es-variants.tsv` | 1,454 | verse-aligned PDF-vs-digital word differences, classified, with Gutenberg arbitration where it applies |
| `es-diff-ledger.tsv` | 829 | same-number comparison ledger, classified |

30,449 of 31,102 verses align identically; 638 differ genuinely; 244 are
character-level near-misses. 15 digital verses have no PDF counterpart
(chapter-boundary bleeds such as Números 13:1 ← 12:16).

## Slugs

`ExaltedBookShort()` is used to build `NETdir://exalted.terminal/r/<short>/…`
URL path segments. The PDF-derived metadata initially carried Spanish names
(`Génesis`, `2 Crónicas` — 37 of 66 with spaces or accents), which would have
produced invalid addresses. Slugs are therefore copied from the canonical
KJV `books.json` (ASCII, `Gen`, `2Chr`) while display names stay Spanish.

## Digital witness is not shipped

`translations/es` is the **PDF-derived build output**. The eBible/wordproject/
BibleAquifer digital text has broken verse numbering (18 empty targets, silent
chapter shifts such as Job 40 running +5, Números 12:16 landing at 13:1) and
one corrupted scan lineage between all three providers. It is rebuilt from
`spaRV1909_usfx.xml` by `reconstruct_digital_es.py` (held at `dist/_held-not-shippable/publishing/reconstruct_digital_es.py` as an audit-witness tool, never run in a build) purely as an audit witness.

## Rebuilding

```bash
# Note: reconstruct_digital_es.py is held (offline-only). Do not run.
python3 scripts/rv1909/build_es_from_pdf.py                 # -> /tmp/opencode/es-pdf
python3 scripts/rv1909/realign_and_variants.py              # -> es-variants.tsv
python3 scripts/gen-exalted-reds.py --src translations/es --book-subdir "" \
    --out <stage> --expect-books 66 --expect-chapters 1189 \
    --expect-verses 31102 --expect-red 0
EXALTED_SITE_SRC=<site tree with Site.reds + data/> EXALTED_LANG_TAG=es \
    EXALTED_SKIP_CET=1 bash scripts/package.sh
```

## Open items

- Wording defects unreviewed (ledger shipped instead) — a later pass with a
  proper Spanish lexicon, using Project Gutenberg #5881 as the NT arbiter (the
  only witness independent of the shared OCR lineage).
- CET surface is still English-only; a Spanish CET build needs its own
  `cache.lua` run.
- `Site.reds` UI chrome is still English; only scripture + book names are
  Spanish. Needs `Rajdhani` glyph coverage checked for the full accent set.
- Non-Latin scripts (Hebrew, Thai, etc.) still unverified.
## Cross-reference lineage finding (important)

**Wikisource's Reina-Valera 1909 is NOT independent of the PDF.** Checked at
Marcos 14 (fetched Oct 4):

| Verse | PDF (shipped) | Wikisource RV1909 | Gutenberg #5881 | digital (eBible) |
|---|---|---|---|---|
| Mc 14:25 | `…aquel día cundo lo beberé…` | `cundo` | `cuando` | `cuando` |
| Mc 14:58 | `…edificaré otro hecho sin mano` | `echo` | `hecho` | `echo` |

So the PDF and Wikisource share a defective OCR ancestry (both carry `cundo`),
while they still diverge from each other at 14:58. Gutenberg — checked against
1922/1925 SBBE/SBA printings — is the only witness found that is independent of
that scan lineage, and it disagrees with both.

**Consequences, and why nothing was rewritten:**

1. The `cundo`-class readings are *not* extraction bugs introduced by this
   pipeline — they are inherited by the whole RV1909 digital family, including
   a library-hosted edition. Treating them as private OCR damage and silently
   "fixing" them would have made this build diverge from its own tradition.
2. The PDF is a faithful rendition of its printed source, including that
   source's defects.
3. For any future wording repair, Gutenberg #5881 is the better NT witness.
   Wikisource is useful for **structure** (it confirmed the 1 Crónicas 21
   boundary) but must not be used as a wording arbiter.

## Post-ship note

Cross-referencing surfaced **Wikisource's machine-readable Reina-Valera 1909**
(`es.wikisource.org/wiki/Biblia_Reina-Valera_1909/`). It was found after the
pilot was packaged, so it changed nothing in the shipped text. It proved useful
for **structure** (1 Crónicas 21) and misleading for **wording** — see the
lineage finding above. Do not treat it as an independent arbiter.
