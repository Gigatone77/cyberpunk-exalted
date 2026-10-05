# EXALTED Translation Versification & Provenance Audit

**Date:** 2026-10-04
**Scope:** all 27 candidate sources in `/var/home/Gigatone/bible-sources/VETTED.txt` (19 marked `BUILD`, 8 `REJECT`).
**Question:** which translations may be converted, shipped and redistributed inside an EXALTED build?
**Canonical reference:** `/var/home/Gigatone/cyberpunk-exalted/cet/EXALTED/data/kjv/` — **66 books / 1189 chapters / 31102 verses**.
**Method:** read-only structural parse of every raw source (OSIS / USFX / Zefania / eBible JSON), raw-vs-build
diff of all 19 shipped trees, full header extraction, and targeted external verification of licence claims.
**Hard rule honoured:** no Bible file was created, modified, moved, re-encoded or deleted. Every number below is
reproducible from `/var/home/Gigatone/versification-audit/out/`.

---

## 1. RED FLAGS — read this before anything else

> **Nothing is shippable today. 14 of 19 candidates are hard-BLOCKED, and the 5 remaining candidates are only
> *conditionally* clean. One single converter bug is responsible for 12 of the 14 blocks.**

### RF-1 — BLOCKER: the converter silently drops the last verse of almost every chapter (12 languages)

`convert_bible.py::_parse_xml_verse_map` resets its verse accumulator at every chapter boundary **without first
flushing the verse that is still pending**:

```python
# /var/home/Gigatone/cyberpunk-exalted/scripts/convert_bible.py, lines 355-362
elif tag == "chapter":
    ...
    cur_v = None          # <-- pending verse discarded
    buf = []              # <-- pending text discarded
```

The pending verse is only written out inside the `verse` branch (line 367) or once more after the book loop
(line 376). A chapter marker therefore **destroys the preceding chapter's final verse**. Only the last chapter
of each book survives, because it is flushed by the post-loop write.

Result: every OSIS-sourced build is missing exactly `chapters − books` verses.

| lang | raw verses | build verses | **lost** | expected `ch − books` | match |
|---|---:|---:|---:|---:|:--:|
| bul | 31101 | 29978 | **1123** | 1189 − 66 = 1123 | exact |
| deu | 31171 | 30048 | **1123** | 1123 | exact |
| fra | 31172 | 30049 | **1123** | 1123 | exact |
| hun | 31170 | 30047 | **1123** | 1123 | exact |
| ita | 31102 | 29979 | **1123** | 1123 | exact |
| mri | 31102 | 29979 | **1123** | 1123 | exact |
| sqi | 31102 | 29979 | **1123** | 1123 | exact |
| swe | 31148 | 30025 | **1123** | 1123 | exact |
| tgl | 31102 | 29979 | **1123** | 1123 | exact |
| tha | 31102 | 29979 | **1123** | 1123 | exact |
| fin | 31107 | 29983 | **1124** | 1190 − 66 = 1124 | exact |
| kor | 30625 | 29520 | **1105** | 1171 − 66 = 1105 | exact |
| chi, cze, dut, por, ron, rus, pol | — | — | **0** | non-OSIS parsers unaffected | clean |

Proof of mechanism, single verse, Italian: raw `ita-riveduta.osis.xml` contains
`<verse osisID='Gen.1.31'>`; the shipped `build/ita/1.json` chapter 1 ends at verse **30**. The entire
verse-by-verse missing-key set is in `out/loss.json` (`lost_detail`, e.g. `1CH` loses `[1,54] [2,55] … [28,21]`).

**This is NOT the known OSIS/Zefania verse-doubling bug.** It is a second, independent, *structural* defect in
the same function. It affects *chapter-final* verses only, whereas doubling repeats a whole verse body. Both
must be fixed before any OSIS language ships. Until then **every OSIS build in `build/` is corrupt and must be
considered unsafe to read as scripture.**

### RF-2 — BLOCKER: `swe-swedish.osis.xml` is truncated AND mislabelled (catastrophic)

The SVD-1917 Unbound module is corrupt in the 1 Peter → Jude range. Chapters keep only a *prefix* of their
verses, and the leftover content is then re-labelled with the wrong book `osisID`:

| div | chapters present | verses/chapter | what the content actually is |
|---|---|---|---|
| `1Pet` | **3** (should be 5) | 21, 22, 18 (should be 25, 25, 22) | 1 Pet, truncated mid-chapter — ends at `1Pet.1.21` |
| `2Pet` | **5** (should be 3) | 10, 29, 24, **21, 21** | 2 Pet (truncated) + **1 John** as `2Pet.4-5` |
| `1John` | **1** (should be 5) | 13 | **2 John** as `1John.1` |
| `2John` | **1** (should be 1) | **15** (should be 13) | **3 John** as `2John.1` |
| `3John` | **5** (should be 1) | 27, 26, 18, 17, 20 | **Jude** as `3John.1-5` |
| `Jude` | 1 | 25 | Jude (correct) |
| `Rev` | 22 | 20,29,22,…,21 | correct |

1 Peter chapters 4–5 do not exist. 2 Peter's chapter count is inflated by 1 John. The shift is a **mislabeling
bug in the source module itself**, not a parser artifact — the `osisID`s are internally self-consistent but
wrong. **A complete local replacement already exists on disk: `SweKarlXII1873-osis.json` (66/1189/31102).**

### RF-3 — BLOCKER: `pol-gdanska.osis.xml` is structurally corrupt (67 book divs for 66 books)

| idx | `osisID` | chapters | first verse |
|---:|---|---:|---|
| 12 | **`2Chr`** | 29 | *"Zmocnił się tedy Salomon…"* (= **1 Chronicles** 1:1) |
| 13 | **`2Chr`** | 36 | identical first verse — duplicate shell |
| 66 | **`1Chr`** | 16 | *"Adam, Set, Enos."* (1 Chr genealogies) — **truncated at 1Chr.16.5, appended at end of file** |

1 Chronicles is **missing from its canonical position**; a 29-chapter 1 Chronicles is mislabelled `2Chr`, and
the genuine (but 16-chapter-truncated) `1Chr` sits at the *end* of the document. A dict-building converter
lets the last writer win, so `1Chr` would resolve to the 16-chapter fragment. `VETTED.txt` nevertheless lists
this file as the `pol` source. **The shipped `build/pol` tree was actually built from
`raw/PolUGdanska-osis.json`, not from this XML** (see `build/pol/build-report.json`), so the corruption never
reached the build — but the registry is wrong and must be corrected.

### RF-4 — BLOCKER: `kor-korean.osis.xml` is truncated mid-book

`2Chr` has **20 of 36 chapters** (−393 verses), `Job` 41 of 42, `1Pet` 4 of 5 (−25 verses). Total 1171 ch /
30625 vs. a complete 1189 / ~31100. **Complete alternatives are already on disk: `KorRV-osis.json`
(66/1189/31104, Korean Revised) and `KorHKJV-osis.json` (66/1189/31102).**

### RF-5 — BLOCKER: `fin-biblia.osis.xml` contains a non-existent chapter

2 Corinthians is numbered `1 … 13, 19`. The chapter `2Cor.19` holds a single verse 15 — a stray fragment.
44 books differ from KJV and 15 chapters carry verse-number holes. No legitimate tradition numbers 2 Cor this
way. **Treat as source corruption, not versification.**

### RF-6 — BLOCKER (rights): Italian Riveduta carries an explicit copyright

`ita-riveduta.osis.xml` header, verbatim:
> `1990 Italian Riveduta Version Copyright (c) 1990 Societa Biblica Britiannica & Forestriera Rome, Italy`

External check agrees the family is reserved: *"Copyright © 1994 Società Biblica di Ginevra. Tutti i diritti
riservati"*, and the Riveduta is credited to *Società Biblica Britannica & Forestiera* / Libreria Sacre
Scritture, ISBN 88-237-1051-0. **Redistribution in a Nexus zip is not permitted.** Keep on disk, never ship.

### RF-7 — BLOCKER (rights): Thai KJV is CC BY-NC-ND — the licence forbids what our pipeline does

`tha-thai.osis.xml` is **not** "Thai LPT" as `VETTED.txt` claims; its header says `KJV-Thai`, `osisIDWork
= kjvthai`, rights pointer to thaipope.org. eBible's record for the identical module (`thaKJV`) states:

> Copyright © 2003 Philip Pope — CC BY-**NC**-**ND** 4.0
> *"You do not sell this work for a profit. **You do not change any of the words or punctuation of the
> Scriptures.**"*

**No-Derivatives is fatal.** The converter strips markup, normalises whitespace and re-encodes; the ND clause
forbids exactly that. Non-commercial also conflicts with paid Nexus distribution. **Preserve on disk, never ship.**

### RF-8 — BLOCKER (rights + lineage): the Albanian text is copyrighted, not public domain

`sqi-albanian.osis.xml` says `<rights>I think public domain</rights>`. That label is **known to be false**:

> *"This text is copyright the Albanian Bible Society (ABS) although it is misleadingly labelled as public
> domain on various websites."* — Wikipedia, *Bible translations into Albanian*

The 1994 "Lajmi i Mirë" / ALBB text also **includes the deuterocanonical books** (dbs.org `ALSSHQ`), violating
the project's deuterocanonical rule, and descends from Dom Simon Filipaj's Catholic-prest work. Three
independent disqualifiers. The `Së bashku` (2007 NT / 2022 full Bible) alternative is explicitly
Catholic+Orthodox+Protestant joint — it also fails a strict non-Catholic lineage test.

### RF-9 — BLOCKER (lineage): Russian Synodal carries deuterocanonical additions

`rus-synodal.zefania.xml` is the 1876 Synodal / 1956 Moscow printing. It has **1192 chapters / 31352 verses**
(+3 ch / +250 vs KJV). Not padding — it is genuine added scripture:

* `DAN` **14** chapters (KJV 12), **530** verses (KJV 357): **Bel and the Dragon** (`DAN.13`) and **Susanna**
  (`DAN.14`) as full chapters; `DAN.3` inflated to 100 verses; `DAN.4` *contracted* 37 → 34.
* `JOL` **4** chapters (KJV 3): Joel 3 is split so the LXX-verse chapter becomes Joel 4.
* `PSA` +67 (superscription verses), `PRO` +4, `JOS` +3, `1SA/1KI/1CH/2CH/JOB` +1 each.
* `ACT` −1 (19:41 merged), `2CO` −1 (13:14 merged into 13:13).

Deuterocanonical material is forbidden by project rule. **A non-deuterocanonical Russian source must be found
or the language dropped.**

### RF-10 — registry and packaging defects

* `VETTED.txt` version strings are **wrong for 3 languages**: `ita` "Riveduta 1927" (file says **1990**),
  `tha` "Thai LPT" (file says **KJV-Thai / Philip Pope**), `hun` "Karoli 1590" (file says only
  *"Hungarian Version"* — no Karoli claim anywhere).
* `pol` registry points at a corrupt XML while the build consumed a different file (RF-3).
* `build/rus/` has **68** JSON files and **no `DISCLOSURE.json`**; every other language has 69 + a disclosure.
* All OSIS languages report `native_names = 0` — book titles are empty, so the UI falls back to English.

---

## 2. Ship / Block decision table

Legend — **BLOCK** = must not ship; **CONDITIONAL** = structurally sound, may ship once §7 gates pass;
**DROP** = no acceptable source obtainable.

| # | lang | version (as filed) | format | raw ch / vs | rights verdict | structural verdict | **DECISION** |
|--:|---|---|---|---|---|---|---|
| 1 | `bul` | Veren's Contemporary Bible | OSIS | 1189 / 31101 | **no rights stmt** | RF-1 | **BLOCK** — RF-1, rights unproven |
| 2 | `chi` | CUV Traditional | USFX | 1189 / 31100 | **no header at all** | clean; 4 books differ | **CONDITIONAL** — needs rights proof |
| 3 | `cze` | Bible kralická | Zefania | 1189 / 31172 | no rights stmt | clean; 11 books differ (PSA +66) | **CONDITIONAL** — needs rights proof |
| 4 | `deu` | Luther 1912 | OSIS | 1189 / 31171 | "We believe … Public Domain" | RF-1 | **BLOCK** — RF-1 |
| 5 | `dut` | Statenvertaling 1637 | Zefania | 1189 / 31079 | no rights stmt | clean; 10 books differ | **CONDITIONAL** — strongest of the Zefania set |
| 6 | `fin` | Finnish 1933/38 | OSIS | **1190** / 31107 | no rights stmt | RF-1 + **RF-5** | **BLOCK** — two independent defects |
| 7 | `fra` | Ostervald 1996 | OSIS | 1189 / 31172 | **"Public Domain"** ✓ | RF-1 | **BLOCK** — RF-1 (rights are fine) |
| 8 | `hun` | *Hungarian Version* | OSIS | 1189 / 31170 | **none** | RF-1 | **BLOCK** — RF-1 + no rights + no version |
| 9 | `ita` | Riveduta 1990 | OSIS | 1189 / 31102 | **© 1990 explicit** | RF-1 | **BLOCK (permanent)** — RF-6 rights |
| 10 | `kor` | Korean Revised | OSIS | **1171** / 30625 | **none** | RF-1 + **RF-4** | **BLOCK** — switch to `KorRV-osis.json` |
| 11 | `mri` | Maori | OSIS | 1189 / 31102 | "i think public domain" | RF-1 | **BLOCK** — RF-1 + weak rights |
| 12 | `pol` | Gdańska | OSIS | — | n/a | **RF-3** corrupt | **BLOCK** for the XML; shipped tree came from `PolUGdanska-osis.json` (clean) |
| 13 | `por` | Almeida pre-1898 | USFX | 1189 / 31098 | **no header** | clean; 10 books differ | **CONDITIONAL** — rights proof required |
| 14 | `ron` | Cornilescu (Protestant) | USFX | 1189 / **31102** | **no header** | **PERFECT — 0 books differ** | **CONDITIONAL** — best candidate |
| 15 | `rus` | Synodal 1876/1956 | Zefania | **1192** / 31352 | no rights stmt | clean parse, **RF-9** deuterocanonical | **BLOCK** — RF-9 |
| 16 | `sqi` | Albanian | OSIS | 1189 / 31102 | **© ABS, "misleadingly labelled PD"** | RF-1 | **BLOCK (permanent)** — RF-8 |
| 17 | `swe` | Swedish 1917 | OSIS | 1189 / 31148 | "i think public domain" | RF-1 + **RF-2** corrupt | **BLOCK** — RF-2; replace with `SweKarlXII1873-osis.json` |
| 18 | `tgl` | Ang Dating Biblia | OSIS | 1189 / 31102 | **"This Bible is now Public Domain."** ✓ | RF-1 | **BLOCK** — RF-1 (rights fine) |
| 19 | `tha` | **KJV-Thai** (not LPT) | OSIS | 1189 / 31102 | **CC BY-NC-ND © 2003 Philip Pope** | RF-1 | **BLOCK (permanent)** — RF-7 licence |
| 20 | `dan` | Danish | OSIS | 1131 / 30139 | "i think public domain" | 61 books — truncated | **DROP** as-is; replacement lead in §6 |
| 21 | `nor` | Norwegian | OSIS | 1148 / 30292 | "i think public domain" | 64 books; Hosea 356 vs 197 verses | **DROP** as-is; replacement lead in §6 |
| 22 | `tur` | Turkish | OSIS | 1187 / 30182 | *no publisher ("nobody")* | 65 books; Obadiah absent | **DROP** as-is; replacement lead in §6 |
| 23 | `lav` | Latvian | OSIS | **259** / 7899 | n/a | **NT only — all 39 OT books absent** | **DROP**; see §6 |
| 24 | `swa` | Swahili (Habari Njema) | OSIS | **255** / 7815 | eBible says PD but **NT-only** | 26 books; Philippians absent | **DROP** — no clean full Bible exists, see §6 |
| 25 | `hrv` | Croatian | OSIS | 1326 / 35437 | — | 73 books | **DROP** — deuterocanonical (correct) |
| 26 | `heb` | Leningrad 26.0 | USFX | 919 / 23046 | — | 38 books, morphologically analysed | **DROP** — OT-only + morphemes (correct) |
| 27 | `lat` | Clementine Vulgate | USFX | 1189 / — | — | — | **DROP** — Catholic source (correct) |

**Tally:** 14 BLOCK · 5 CONDITIONAL (`chi` `cze` `dut` `por` `ron`) · 8 DROP · **0 shippable today.**

The single highest-value action is fixing the one converter bug in RF-1: it alone unblocks `bul`, `deu`,
`fra`, `hun`, `mri`, `tgl` (6 languages, rights permitting).

---

## 3. Question 2 — why do many languages report identical verse deltas?

**Observed:** `bul`, `deu`, `fra`, `hun`, `ita`, `mri`, `sqi`, `tgl`, `tha` (and `fin`, `swe`) all show the same
per-book shortfall, e.g. **Genesis 1484** against a canonical 1533.

**Answer: it is neither shared text lineage nor coincidence in the translations. It is the RF-1 converter bug,
applied to sources that mostly agree on structure anyway.**

The arithmetic is exact and per-book. Genesis has 50 chapters, so `chapters − books = 50 − 1 = 49` verses are
destroyed: `1533 − 49 = 1484`. ✓ The same identity holds for every other book and every one of the 11 languages
(raw totals differ by small amounts — `bul` 31101, `ita` 31102, `fra` 31172 — so their *totals* are **not**
identical, only their per-book Genesis figure is).

**The decisive evidence** is where the deltas *stop* agreeing. Every genuine structural difference in the raw
text shows up as a divergence from the `−(ch−1)` prediction:

| lang | raw diff from KJV | predicted loss | observed build delta | diagnosis |
|---|---:|---:|---:|---|
| `bul` | −1 (only `1SA`) | 1123 | 1124 | exactly the raw diff |
| `fra` | +70 (`PSA` +67, `MRK` +2 …) | 1123 | 1053 | raw diff absorbed |
| `hun` | +68 (`PSA` +66, `HAG` −1 …) | 1123 | 1055 | raw diff absorbed |
| `fin` | +5 **+1 chapter** | 1124 | 1119 | RF-5 chapter |
| `kor` | −477 **−18 chapters** | 1105 | 1582 | RF-4 truncation |

If the languages shared a *textual* base, these rows would move together. They move apart exactly as the
independent raw sources predict. **Shared lineage is therefore excluded.**

### What *is* shared: an OSIS packaging convention

Five sources are **byte-identical in structure to KJV** — same 66 books, same 1189 chapters, same per-book and
per-chapter verse counts, zero differences anywhere:

> `ita` · `mri` · `sqi` · `tgl` · `tha` → all **66 / 1189 / 31102**

That is a strong signal they were generated from the **same English OSIS/KJV skeleton** (ebible/Unbound
toolchain). It is a statement about **packaging**, not about wording or textual descent. It is useful for one
purpose — it means these five can be cross-checked against each other cheaply — and useless for another:
it says nothing about wording, and it must not be used to justify shipping them (three of the five are
permanently blocked on rights: `ita`, `sqi`, `tha`).

---

## 4. Book-level versification register (raw sources)

Classified as **TRADITION** (a real, named versification — ship with a ledger), **TEXTUAL** (a textual variant,
not a numbering difference — ship with a note), or **CORRUPT** (no tradition produces it — block).

### 4.1 CORRUPT — must not ship in this form

| source | evidence |
|---|---|
| `swe` | 1Pet 3 ch, 2Pet 5 ch, 1John 1 ch, 3John 5 ch, chapters truncated mid-book — RF-2 |
| `kor` | 2Chr 20/36 ch, Job 41/42 ch, 1Pet 4/5 ch — RF-4 |
| `pol` (XML) | 67 book divs; 1Chr mislabelled `2Chr`; real 1Chr truncated to 16 ch at EOF — RF-3 |
| `fin` | `2Cor.19` non-existent chapter; 44 books differ; 15 verse-number holes — RF-5 |
| `dan` | 61 books; Obadiah, Philemon, 1/2/3 John, Jude absent; Psalms 99/150 |
| `nor` | 64 books; Proverbs + Song absent; Hosea 356 verses vs KJV 197 |
| `tur` | 65 books; Obadiah absent; Malachi 3/4 truncated |
| `lav` | 27 books; **entire OT absent**; Mark 15/16 |
| `swa` | 26 books; **entire OT + Philippians absent**; Matthew 27/28 |

### 4.2 TRADITION — legitimate re-versification, ship with a published ledger

**Psalm superscriptions counted as verse 1** (shifts every subsequent Psalm by +1):
`deu` **+67** (63 chapters) · `fra` **+67** · `hun` **+66** · `cze` **+66** · `fin` **+65** · `swe` **+65** ·
`rus` **+67**. This is the standard *Lutheran / liturgical* practice, not an error.

**Joel 4** (LXX-aligned, Joel 3 split): `deu` 3→4 ch · `hun`? no · `rus` 3→4 ch. `mal` 4→3 ch in `deu`
(Luther merges Malachi 4 into 3:24) — both are standard *German/Lutheran* divisions.

**Older national versifications:**
* `dut` (Statenvertaling 1637, pre-standardisation): `JOB` 1058 vs 1070 (−12), `HOS` 194 vs 197 (−3),
  `DAN` 356, `ISA` 1291, `ECC` 221, `MIC` 104, `ACT` 1006, `2CO` 256, `EXO` 1212, `1SA` 809. The old Dutch
  versification predates the 1870 international standard — expected and citable.
* `cze` (Bible kralická, 1613): `PSA` 2527, `1SA` 811, `1KI` 817, `JOB` 1071, `ECC` 223, `JHN` 880,
  `3JN` 15, `REV` 405, `EXO` 1212, `ACT` 1006, `2CO` 256.
* `por` (Almeida pre-1898): `GEN` −2, `NUM` −2, `NEH` −1, `EZK` −1, `LUK` −1, `2CO` −1; `JDG` +1, `1SA` +1,
  `3JN` +1, `REV` +1.
* `chi` (CUV 1919): only 4 books differ — `DEU` −1, `PSA` −1, `JHN` −1, `3JN` +1. Minimal, well documented.
* `bul` (Veren, collated from 1871): **one** book differs — `1SA` 809 vs 810. Essentially KJV-aligned.
* `hun`: `HAG` 37 vs 38 (−1) — a single real hole at `HAG 2:18` (see §4.4).

### 4.3 TEXTUAL variants — real scripture differences, note them

Shared across `cze` `dut` `fra` `hun` `rus` `por` `chi`:
* **`ACT` 19:41 merged** — the *"we all sailed"*/`ἐπέβησαν` clause is folded into v.40 → −1 verse.
* **`2CO` 13:14 merged** into 13:13 (Paul's benediction) → −1 verse.
* **`3JN` 1:15 / `REV` 12:18** gains a closing clause → +1 verse.
* **`REV` 12:17-18** split → +1 verse (`cze` `fra` `hun` `por`).

### 4.4 GENUINE HOLES — flagged by the converter, must be explained not ignored

All three are **source-faithful omissions**, not build damage: the converter reproduces the source exactly, so
`build/*/DISCLOSURE.json` correctly lists **no substitutions**. They still need ledger entries.

* `fin` — exactly 15 chapters carry a missing verse number, and every one is a standard Textus Receptus
  omission (measured, not assumed):
  `2CH 23:4` · `MAT 17:21` · `MAT 18:11` · `MAT 23:14` · `MRK 9:44,46` · `MRK 11:26` · `MRK 15:28` ·
  `LUK 17:36` · `LUK 23:17` · `JHN 5:4` · `ACT 8:37` · `ACT 15:34` · `ACT 24:7` · `ACT 28:29`.
* `hun` — 1 hole: `HAG 2:18`.
* `swe` — 3 holes: `LUK 20:22`, `LUK 23:17`, `ACT 28:29`. The build additionally reports 17 `unfilled_gap`
  disclosure entries, so this source has gaps beyond the three numbering holes.

**Note:** because these omissions are inherited from the source rather than introduced by the build, the
`DISCLOSURE.json` files are legitimately empty. Do **not** read an empty disclosure as "this language is
complete" — it only means the build introduced no substitutions of its own.

---

## 5. Provenance & rights register (exact header fields)

Extracted verbatim from `out/provenance.json`. **Bold** = a rights statement that is missing, hedged, or adverse.

### 5.1 OSIS sources (real `<header>` present)

| lang | `<work osisID>` | `<title>` | `<publisher>` | `<rights>` |
|---|---|---|---|---|
| `bul` | `BulVeren` | Veren's Contemporary Bible | *(absent)* | **— none —** |
| `deu` | `luth1912` | Luther 1912 | FREE BIBLE SOFTWARE GROUP | "We believe that this Bible is found in the Public Domain." |
| `fra` | `ostv1996` | La Bible J.F. Ostervald 1996 | FreeBibleSoftwareGroup | **"Public Domain"** ✓ |
| `hun` | `hun` | Hungarian Version | Free Bible Software Group | **— none —** |
| `ita` | `IRV_1990` | Riveduta 1990 | FREE BIBLE SOFTWARE GROUP | **"1990 Italian Riveduta Version Copyright (c) 1990 Societa Biblica Britiannica & Forestriera Rome, Italy"** |
| `kor` | `kor` | Korean Version | Free Bible Software Group | **— none —** |
| `mri` | `MAO` | Maori Version | FREE BIBLE SOFTWARE GRUOP *(sic)* | "i think public domain" |
| `sqi` | `alb1` | Albanian Version | Free Bible Software Group | **"I think public domain" — but © ABS (RF-8)** |
| `swe` | `SVD` | Swedish 1917 Version | FREE BIBLE SOFTWARE GROUP | "i think public domain" |
| `tgl` | `TlgAngBiblia` | Ang Dating Biblia | Theologische Initiative Freiburg | **"This Bible is now Public Domain."** ✓ |
| `tha` | `kjvthai` | KJV-Thai | "Your Organisation" | **thaipope.org → CC BY-NC-ND © 2003 Philip Pope** |
| `fin` | `fin` | Finish Version *(sic)* | Free Bible Software Group | **— none —** |

**Structural identity (Q2):** `ita` `mri` `sqi` `tgl` `tha` are byte-identical to KJV structure (66/1189/31102).
All six `<date>` values are `2010-02-26` / `2009-01-20`, all `ZefToOsis 1.0.0` — one generation batch.

**Lineage flags:** `bul` — Veren LTD, CDL Project, 1871 Fotinov/Slaveykov/Sichan-Nikolov (Protestant) ✓.
`mri` — *"Maori Bible prepared by Timothy Mora. Text reproduced by Dr. Cleve Barlow"* — a **modern
reproduction of an older translation**, so the 2010 date is an encoder date, not a translation date;
public-domain status of the *reproduction* is unproven. `hun` — header says nothing about Karoli;
`VETTED.txt`'s "Karoli 1590" is **unsupported by the file**.

### 5.2 Zefania sources (`<INFORMATION>`, no rights field at all)

| lang | `<title>` | `<identifier>` | `<date>` | `<contributors>` / `<source>` | rights |
|---|---|---|---|---|---|
| `cze` | Bible Kralická | `CZBKR` | 2016-10-10 | creator `Pan Tau`; contributors `unbound` | **none** |
| `dut` | Dutch Statenvertaling | `DUTV` | 2009-01-20 | description: Dordrecht 1618/19 States-General decree | **none** |
| `rus` | Russian Synodal Translation | `RST` | 2009-01-20 | *"1876 Russian Synodal Translation, 1956 Edition — The text was supplied by 'Light in East Germany'."* creator `Jens Grabner`; source agape-biblia.org / crosswire.org | **none** |

The `dut` description is a genuine provenance document (the 1618/19 synodical translation order) — the
strongest lineage evidence of any Zefania source. None of the three carries a rights statement.

### 5.3 USFX sources (eBible — **no header element whatsoever**)

`chi-cuv.usfx.xml` (3,951,359 B) · `por-almeida.usfx.xml` (4,745,976 B) · `ron-rccv.usfx.xml` (4,697,599 B).

All three are bare eBible USFX with **zero embedded provenance or rights metadata**. Nothing in the file
establishes redistribution terms; everything must come from the eBible catalogue record. `ron` is the only
candidate whose structure is a perfect 66/1189/**31102** match to KJV.

### 5.4 eBible JSON dumps (scrollmapper format — **no header, top-level key `books` only**)

`PolUGdanska-osis.json` (15,100,087 B) · `KorRV-osis.json` (11,791,134 B) · `KorHKJV-osis.json` (13,222,562 B) ·
`SweKarlXII1873-osis.json` (11,449,207 B) · `Swe1917-osis.json` (16,578,588 B) · `AKJV-osis.json` (12,983,528 B).

These are the **best structural replacements already on disk** (§6) — and none of them can be shipped until
its eBible catalogue record is checked for a licence. `Swe1917-osis.json` carries **83 books / 1397 ch /
37791 verses** = it includes the Apocrypha → **not** suitable.

---

## 6. Replacement leads

### 6.1 Already on disk — act on these first

| need | use | structure | caveat |
|---|---|---|---|
| Korean (RF-4) | **`KorRV-osis.json`** — Korean Revised, matches the registry's own claim | **66 / 1189 / 31104** | no header → verify eBible record |
| Korean alt | `KorHKJV-osis.json` | 66 / 1189 / 31102 | same |
| Swedish (RF-2) | **`SweKarlXII1873-osis.json`** — Karl XII 1873 | **66 / 1189 / 31102** | no header → verify eBible record |
| Polish (RF-3) | **`PolUGdanska-osis.json`** — *already the actual build source* | **66 / 1189 / 31102** | correct `VETTED.txt` entry to this file |

### 6.2 Rejected, no local replacement — external leads (time-boxed research required)

* **`dan`** — the local file is an eBible OSIS module (mirrored by `seven1m/open-bibles`, which lists it
  *"Danish Bible — Public Domain"*). The truncation is a **download fault, not a source fault**: re-fetch the
  eBible module (`ebible.org` hosts OSIS, USFX and Crosswire Sword zips; `dan1931` = *Hellig Bibel*) and verify
  66 books before abandoning Danish.
* **`nor`** — same eBible/OSIS situation; re-fetch and verify. **Watch out:** Hosea at 356 verses is *not* a
  plausible Norwegian versification and suggests the same truncation class as `dan`. Treat as suspect even
  after re-fetch.
* **`tur`** — header publisher is literally *"nobody"*; provenance is unusable. The real candidate is
  **Kutsal Kitap Yeni Çeviri (2001, rev. 2008)**, produced with the Bible Society of Turkey + The
  Translation Trust + Yeni Yaşam Yayınları (translation-trust.org history; find.bible `TURBST`). It is
  Protestant and modern, but **copyright** — obtain permission or drop.
* **`lav`** — the local file is `latvian_nt_utf8.zip`: **New Testament only**. A complete rights-clean Latvian
  Bible does not appear to exist in the eBible/Unbound corpus. Full Latvian Bibles are Latvijas Bībeles
  biedrība publications (1965 rev. 1997, and a 2012 revision published 2024) — all **in copyright**. Treat
  Latvian as **DROP** unless the user supplies a copy with redistribution rights.
* **`swa`** — **no clean full Bible exists.** The only free Swahili is the 1850 Krapf **New Testament**
  ("Habari Njema"), which is exactly why the local file has 26 books. eBible `swh1850` is public domain but
  NT-only; the complete *Biblia Takatifu* (1979, Bible Societies of Kenya/Tanzania) is under copyright, and
  the modern eBible Swahili modules (`swhulb`, `ONEN`, `ONMM`) are **licensed, not free**. **DROP.**
* **`sqi`** — the only complete, modern, non-Catholic Albanian is `Së bashku` (2007 NT / 2022 full Bible), but
  it is explicitly Catholic+Orthodox+Protestant joint, so it **fails the C2 non-Catholic gate**. No compliant
  Albanian source is likely to exist. **DROP unless the user relaxes C2.**
* **`ita`** — a public-domain Italian Riveduta/New Riveduta does not exist; the family is reserved to
  Società Biblica Britannica & Forestiera / Società Biblica di Ginevra. Consider **Diodati 1769 / 1991**
  (Protestant, older, potentially PD) as an Italian substitute — **requires its own rights check.**
* **`tha`** — the CC BY-NC-ND KJV-Thai cannot be adapted. A CC-permissive or PD Thai Bible would be needed;
  none identified. **DROP unless a licence-clean Thai source is produced.**

---

## 7. Pre-ship checklist (nothing ships until every box is ticked)

1. **Fix RF-1** in `convert_bible.py::_parse_xml_verse_map` — flush the pending verse *before* resetting
   `cur_v`/`buf` on a chapter boundary. Rebuild every OSIS language.
2. **Re-verify** each rebuilt tree: `lost == 0` against its own raw source, `gained == 0`, chapter counts equal
   the raw source, 0 empty verses, 69 files, `DISCLOSURE.json` present (fixes `build/rus`).
3. **Fix RF-3 registry** — point `VETTED.txt`'s `pol` row at `PolUGdanska-osis.json`; correct the `ita`
   (1990), `tha` (KJV-Thai) and `hun` (no Karoli claim) version strings.
4. **Rights gate per language** — a *positive, citable* licence record for every shipped language. Missing or
   hedged rights (`bul` `hun` `kor` `fin` `mri` `sqi` `swe` `cze` `dut` `rus` and all USFX/JSON sources) =
   no ship. Attribution strings must be written into the build, not just the docs.
5. **Deuterocanonical gate** — reject `rus` (Dan 13/14, Joel 4) and `sqi` (full apocrypha) unless a
   non-deuterocanonical replacement is found.
6. **Ledger gate** — every TRADITION and TEXTUAL difference in §4 must appear in a shipped per-language
   reference ledger so in-game citations resolve correctly. `PSA` superscription shifts affect *every* Psalm
   reference in `deu` `fra` `hun` `cze` `fin` `swe` `rus`.
7. **Font/render gate** — Thai was explicitly flagged as an unproven font route; CJK (`chi`), Hebrew (n/a),
   Devanagari-free set, and Thai/CJK line-breaking must be verified in-game before a language pack is published.
8. **ATTRIBUTION + licence text shipped** — required for `tha` (CC BY-NC-ND, if ever used), `tgl`,
   `deu`, `fra` and any CC-licensed source.

---

## 8. Evidence index

| Artefact | Path |
|---|---|
| registry under audit | `/var/home/Gigatone/bible-sources/VETTED.txt` |
| raw sources (read-only) | `/var/home/Gigatone/bible-sources/raw/` |
| shipped trees under audit | `/var/home/Gigatone/bible-sources/build/<lang>/` |
| converter with the RF-1 defect | `/var/home/Gigatone/cyberpunk-exalted/scripts/convert_bible.py` (lines 318-378) |
| canonical structure | `/var/home/Gigatone/cyberpunk-exalted/cet/EXALTED/data/kjv/` |
| canonical book metadata | `/var/home/Gigatone/cyberpunk-exalted/cet/EXALTED/data/books.json` |
| raw source counts | `/var/home/Gigatone/versification-audit/out/raw_sources.json` |
| build counts | `/var/home/Gigatone/versification-audit/out/summary.json` |
| **raw-vs-build loss proof (RF-1)** | `/var/home/Gigatone/versification-audit/out/loss.json` |
| per-book versification register | `/var/home/Gigatone/versification-audit/out/raw_versification.json` |
| header extraction | `/var/home/Gigatone/versification-audit/out/provenance.json` |
| analysis scripts (throwaway) | `/var/home/Gigatone/versification-audit/0{1..7}_*.py` |

**External sources consulted (2026-10-04):**
`ebible.org` `thaKJV` record + about page · `thaipope.org` · Wikipedia *Bible translations into Albanian* ·
`dbs.org/bibles/ALSSHQ` · *4enoch.org* Filipaj entry · Christian Post *Albanian Translation of NT* ·
`translation-trust.org/history-of-turkish-bible` · `find.bible/bibles/TURBST` · `bible.com` TCL02 ·
`ebible.org/bible/details.php?id=swh1850` · `seven1m/open-bibles` index · `ebaznica.lv` Latvian Bible
history (1965/1997/2012 revisions, Latvijas Bībeles biedrība).

**Scripting note:** `05_versification.py` has a known top-level `d_verses` arithmetic fault (`kjv_vs` was
initialised to the chapter count `1189` instead of `31102`). The **per-book** rows and every total quoted in
this document were recomputed independently and are correct; ignore the top-level `d_verses` field in that
JSON file.