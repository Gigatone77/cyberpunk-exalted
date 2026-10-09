# EXALTED Terminal 77 — Language Source Registry

**Status: AUTHORITATIVE for language/source state. Read this before touching
`scripts/convert_bible.py`, `scripts/gen-exalted-reds.py` or `scripts/package.sh`.**

Last verified: **Oct 4** against the on-disk evidence named in §9. Every number
in this file was read out of `VETTED.txt`, `bible-sources/raw/*.xml|json`
headers, `bible-sources/build/<lang>/build-report.json`, `translations/<lang>/`
and `dist/`. Nothing here is assumed.

Companion docs: `docs/MULTILINGUAL-PLAN.md` (design + phases), 
`docs/RV1909-SOURCE.md` (the Spanish provenance story), `docs/CREDITS.md`
(licensing text that must be updated per shipped language).

---

## 1. Tallies

| Bucket | Count | Languages |
|---|---|---|
| **SHIPPED** (artifact exists in `dist/`) | 2 | `en`, `es` |
| **STAGED browser zips (built 2026-10-05, staged 2026-10-06)** | 6 | `cze deu dut pol rus swe` — localized docs exist for `cze dut rus` only (2026-10-08), the rest held on §4b; a 7th zip, `heb` (**REJECTED**, §6), was moved out of staging into `_superseded/` on 2026-10-08; see §4 |
| **BUILT-NOT-PACKAGED** | 19 | `bul chi cze deu dut fin fra hun ita kor mri pol por ron rus sqi swe tgl tha` |
| **VETTED-NOT-BUILT** | **0** | every `BUILD` row in `VETTED.txt` has a `build/<lang>/` dir |
| **REJECTED** (reason recorded, never silently dropped) | 7 | `dan hrv heb lat lav nor swa tur` |
| Not yet vetted (named in the plan, no source on disk) | 4 | `ja ar uk` + Turkish is rejected above |

Of the 19 built languages, only **5 are actually package-ready today**
(`chi cze dut por rus` — genuine native book names; `ron` was removed
2026-10-06). The other **13** put
English book names in front of foreign scripture — see §4b. `pol` is the odd
one out: its *source* lists the books in English, so that one is a source-data
problem, not a parse problem.

---

## 2. What "supported" means here (surfaces + in-game dependencies)

EXALTED has **two independent surfaces**. A language can be live on one and
dead on the other, which is exactly the Spanish situation.

| Surface | Ships to | In-game dependency | Language-ready? |
|---|---|---|---|
| **Browser** — the `NETdir://exalted.terminal` site | `r6/scripts/EXALTED/` | **Browser Extension Framework, Nexus mod 10038** (0.9.7+), which itself needs `redscript`, `RED4ext`, `Codeware` (optional: Mod Settings) | Per-language. This is what a language build replaces. |
| **CET terminal** — hotkey + ImGui overlay | `bin/x64/plugins/cyber_engine_tweaks/mods/EXALTED/` | **Cyber Engine Tweaks** (CET) | **English only.** `cache.lua` builds from `cet/EXALTED/data/` and has no per-language path. A translated CET surface needs its own `cache.lua` build. |

Consequences recorded in this file:

- Every language artifact so far is **browser-only** (`EXALTED_SKIP_CET=1`).
- The browser surface is **redscript + the framework, no Lua**, so a language
  payload is pure data — that is why `scripts/package.sh` can swap it safely.
- `Site.reds` **UI chrome is English for every language** (About page, "OPEN
  LIBRARY", "HOME", "NEXT PAGE", the browser `shortName`). Only scripture text
  and the book index are localized. This is a known gap, not a bug.

---

## 3. SHIPPED

| code | Language | English name | Version / edition | Tradition | Rights verdict + evidence (✅=clear, 🟠=judgement call, 🔴=blocked) | Canonical source | sha256 | Converter format | Build status | Artifact | Blockers |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `en` | English | English | King James Version 1611 / Oxford 1769 | Protestant / Anglican | **PD — stated in-repo.** `docs/nexus-description.bbcode.txt:82` credits "Project Gutenberg; Crosswire/eBible.org"; NKJV (© Thomas Nelson) is explicitly **not** used | `cet/EXALTED/data/kjv/*.json` (canonical, 66 files) | see §9 note | in-repo exporter (`scripts/`) | SHIPPED, all three surfaces | `EXALTED_Terminal_77-AllInOne-0.1.5.zip` `99a927523616eaf0940ea9291c6087592ac223f861f2425b8ff778c27685c094` (**now the ONE multi-language mod: CET 0.1.5 + the browser site for en, es, cze, deu, dut, pol; runtime `/`-code switch**)<br>`EXALTED_Terminal_77-Browser-MultiLang-0.1.2.zip` `c5b1451e05ee3c37a1ee7e32d65d054d6233e0b6125f348227fa49b5167f4fc0` (browser site only, same six languages)<br>`EXALTED_Terminal_77-CET-0.1.5.zip` `fba32fb74032f697b9dcc59227836ff88015512eb5fae6c7de7fade570bb9fce`<br>`EXALTED_Terminal_77-Browser-0.1.2.zip` `2eb996b7adde4d8f583d853abf1d6e0d98f46cf25a41b64dd233141997acd9ca` (English) | in-game render test never run |
| `es` | Spanish | Spanish | **Reina-Valera 1909** (printed PDF) | Protestant | **PD — verified by orthographic fingerprint**, not by an imprint (the PDF has none). `fué`×1733, `á` preposition×18977, `Jehová`×6782, `vosotros`×1652, `ustedes`×0. Full argument: `docs/RV1909-SOURCE.md` | printed PDF `Documents/20/Bibles/Spanish.zip` | `1d8545c59c5c77debce3654f7a4641a79a83bc0db03490af197fccf683b4507d` | PDF → `scripts/rv1909/build_es_from_pdf.py` | SHIPPED, **browser only** | `EXALTED_Terminal_77-Browser-es-0.1.2.zip`<br>`d108256cae1151e3dd60b8b08429128668ce4ddb1dbf5e1b3548be2ce1e29acf` | ① **Spanish `Site.reds` chrome still English.** ② **Spanish CET surface does not exist** (English only). ③ in-game render test still owed. ④ 1,454 OCR-class wording defects shipped as-is + ledger (`scripts/rv1909/es-variants.tsv`) |

> **Correction 2026-10-09:** the `en` row's artifact hashes were **stale** (they
> predated the Oct 6 rebuild) and are refreshed above against the staged zips;
> the unified zip was renamed `EXALTED_Terminal_77-0.1.5.zip` →
> `EXALTED_Terminal_77-AllInOne-0.1.5.zip`. Re-verify with
> `sha256sum -c` in the staging dir before any upload.
>
> **Correction 2026-10-09 (b):** the All-in-One is now the ONE **multi-language**
> mod (user directive: "all-in-one is not multiple mods, it is one mod with all
> of the languages"). It ships the CET surface plus a **combined** browser tree
> built by `scripts/langify.py` — `r6/scripts/EXALTED/data/ExaltedLang.reds`
> dispatches six per-language modules (`ExaltedData{En,Es,Cze,Deu,Dut,Pol}`),
> selected at runtime by the NETdir address (`/es`, `/cze`, …; bare address =
> English). The old English-only combo of the same version is preserved at
> `_superseded/EXALTED_Terminal_77-AllInOne-0.1.5.english-combo.zip`
> (`4f7185f7…`) and in `~/gt77-backups/exalted/20261009-allinone-english-pre/`.
> The six per-language browser zips are unchanged (they still ship the
> single-language `Site.reds`); only English is user-verified, the other five
> share the identical generated structure, so they are trusted by construction
> (`docs/MULTILANG-WIP-20261004.md`).
>
> **Correction 2026-10-09 (c):** `deu` and `pol` no longer fall back to English
> book names. Their source builds carried `native_names: 0` (deu: OSIS with no
> headings; pol: its JSON lists English book names itself), so native display
> names were supplied — German per **Luther 1912** (`1. Mose … Offenbarung`) and
> Polish per **Biblia Gdańska** (`Rodzaju … Objawienie Jana`) — into
> `bible-sources/build/{deu,pol}/books.json` + `translations/{deu,pol}/books.json`
> (canonical KJV `short` slugs untouched, asserted). Their standalone browser
> zips were rebuilt and the multi-language pack regenerated:
> `Browser-deu-0.1.2.zip` `cb9ce9ff68d80f4dac9ae2a20b35e7e864a08ee19a053a4b403ae16b86cc7652`,
> `Browser-pol-0.1.2.zip` `805dd2cd4464498f0cc87ce4fdfaf3600fe22be888681c2f32910af335e18b3e`;
> All-in-One `99a92752…`, Browser-MultiLang `c5b1451e…` (above). The previous
> English-named deu/pol zips are stashed at `_superseded/…english-names.zip`;
> build metadata backed up in
> `~/gt77-backups/exalted/20261009-deu-pol-native-names-pre/`. `swe` still ships
> English names (its rebuild status is separately unresolved) and `heb` is still
> rejected (§6).

English + Spanish are the only languages with a **user sign-off on the version**
(plan constraint C4).

---

## 4. BUILT-NOT-PACKAGED

All 19 converted and verified by `scripts/convert_bible.py`
(`bible-sources/build/<lang>/`), all re-generated + packaged + slug-gated
during the Oct 4 packaging audit.

**CORRECTION 2026-10-08 (the old text here said "no artifacts exist" — that
stopped being true on Oct 5).** Browser zips now exist for six of these —
built 2026-10-05, staged 2026-10-06 in `dist/`,
`installer-usb/nexus-upload/EXALTED-Terminal-77/` and the ToolBox mirror:
`cze deu dut pol rus swe`. A seventh zip, `heb`, is **REJECTED** (§6) and was
moved out of the upload staging root into `_superseded/` on 2026-10-08 (move,
never rm) so it cannot be uploaded by accident. Localized `DESCRIPTION-…` /
`INSTALL-…` text exists
for `en`, `es` and — written 2026-10-08 — `cze dut rus`; the remaining ones are
held: `swe` on English book names (§4b), `heb` on §6. (`deu` and `pol` were
held on English names too but were **resolved 2026-10-09** — see note (c) — and
now ship native headings.)

Book names above were verified **from the staged zips themselves**
(`r6/scripts/EXALTED/data/ExaltedData.reds`), not from the build reports:
native = `cze dut rus heb deu pol`; English fallback = `swe` only. `rus` is
package-ready on names but still carries the §7 font blocker (`Site.reds`
hardcodes `raj.inkfontfamily`), so its INSTALL discloses the risk.

`flags` = per-book verse-count deltas vs canonical KJV in `build-report.json`.
`disc.` = `disclosure` entries (`unfilled_gap`). `native` = books whose display
name is the language's own, not the English fallback.

### 4a. Package-ready (native book names resolved) — 7

| code | Language | English name | Version / edition (declared in source header) | Tradition | Rights verdict + evidence | Canonical source | sha256 (raw) | Format | Books / chapters / verses | native | flags | disc. | zip bytes | data MiB | Blockers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `por` | Portuguese | Portuguese | **nothing is declared** — no title, no date, no identifier element. "pre-1898 Almeida" is a **filename-only** claim, ratified by user decision (plan §6.1) | Protestant | **PD by user decision (plan §6.1)**; source carries **zero** metadata — provenance rests on filename + decision. 10 verse-count deltas | `raw/por-almeida.usfx.xml` | `4990d0d1909e2bd57aa6ecc2a2ce9a565b154aac8575b0242dc943ad796e643e` | usfx | 66 / 1189 / 31098 | 62 differ from KJV | 10 | 0 | 1467596 | 4.0 | Provenance unproven in-file; **next language to ship** |
| `ron` | Romanian | Romanian | **nothing is declared** — no title/date/identifier. "Cornilescu (Protestant)" is **filename-only** | Protestant | **No metadata element at all**, no rights statement. PD assumed from 19th-c. Protestant lineage | `raw/ron-rccv.usfx.xml` | `c0da17b46dcfc4aaa55bebf752fece646e381824a71675e6784bdc5acc3ab507` | usfx | 66 / 1189 / 31102 | 61 differ from KJV | 0 | 0 | 1527736 | 4.3 | **REMOVED 2026-10-06 (user order)** — unattested source, never shipped; tree + history purged, see note below (§VETTED) |
| `rus` | Russian | Russian | `<contributors>`: "**1876** Russian Synodal Translation, **1956 Edition** — the text was supplied by Light in East Germany" (`title` = "Russian Synodal Translation", `identifier` = RST) | Orthodox / Protestant-tradition | `<rights>` element present but **empty**; distributor address is agape-biblia.org / crosswire SWORD. 1876 PD; the 1956 supplying edition is an assumption | `raw/rus-synodal.zefania.xml` | `5ccd097980d85790d36525859cc9092ba7a31671dcdd46e4fa659f1d7fa57769` | zefania | 66 / **1192** / **31352** | 66 differ from KJV | 13 | 0 | 1704968 | 6.1 | ① **Versification differs from KJV** (1192 ch / 31352 v; e.g. Daniel 14 ch/530 v). Needs the same style of adjudication as 2 Cr 16 / 1 Cr 21. ② needs the `Site.reds` per-language font map (§7) |
| `dut` | Dutch | Dutch | `title` "Dutch Statenvertaling", `identifier` **DUTV**; description quotes the Synod of Dordrecht decree of 1618/1619 but **declares no year** (1637 is standard reference knowledge, not in-file) | Reformed | `<rights>` element present but **empty**; 17th-c. state-translation text | `raw/dut-statenvertaling.zefania.xml` | `aa7780e583b2aa9c9fc18beba823c09d60d5fd3245db69eebe074f4bd2c72e7f` | zefania | 66 / 1189 / 31079 | 58 differ from KJV | 10 | 0 | 1526771 | 4.4 | 10 verse-count deltas need a read-through |
| `cze` | Czech | Czech | `title` "**Bible Kralická**" (`CZBKR`); description: "…podle posledního vydání Kralického **z roku 1613**" | Protestant | `<rights>` element present but **empty**; 1613 PD | `raw/cze-bkr.zefania.xml` | `4fc19dc75313994860662ac142690ba7ab84a279db3815182e77d374baaa4cbd` | zefania | 66 / 1189 / **31172** | 58 differ from KJV | 11 | 0 | 1541084 | 4.0 | 11 verse-count deltas; diacritics in display names only |
| `chi` | Chinese | Chinese | **nothing is declared** — the USFX has no title, date or identifier. "CUV Traditional" is **filename-only** | Protestant | **No metadata element at all.** Version is a filename-only claim; nothing to check against | `raw/chi-cuv.usfx.xml` | `049e36ec3ee1b5c9bc2c8bfd2ca07f9f1f30398838f692d12ea38a092d41fe4b` | usfx | 66 / 1189 / 31100 | 66 differ from KJV | 4 | 0 | 1320466 | 3.3 | ① **Hard non-Latin blockers** — see §7 |

### 4b. Built but BLOCKED on display names — 13

12 of these 13 are **`osis` sources where the converter resolved 0/66 native
headings and fell back to the canonical English names**
(`build-report.json` → `native_names: 0`, `english_name_fallback`: all 66 ids).
That contradicts plan §3 ("we never ship English book names with a foreign
text"). The per-book verse-count `flags` are also the highest in the set
(61–79 per language), consistent with an OSIS parse that is losing or merging
verses. `pol` is the 13th and fails **differently** — its source JSON lists the
books in English itself, so no converter can recover Polish names from it
(needs either a Polish heading list supplied alongside, or the sibling
`raw/pol-gdanska.osis.xml`).

**RESOLVED 2026-10-09 for `deu` and `pol`** (note (c)): native heading lists
were supplied (Luther 1912 / Biblia Gdańska), the builds and standalone zips
rebuilt, and both now ship in the multi-language pack. The `deu`/`pol` rows
below are therefore historical; the heading blocker is cleared. `swe` and the
other entries in this table remain unresolved.

| code | Language | English name | Version / edition (declared) | Tradition | Rights verdict + evidence | Canonical source | sha256 (raw) | Format | ch / verses | flags | zip bytes | Blockers |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `deu` | German | German | `title` "**Luther 1912**", `identifier` luth1912, description "Lutherbibel von 1912" | Lutheran / Protestant | ✅ `<rights>We believe that this Bible is found in the Public Domain.</rights>` — asserted by the Free Bible Software packager, consistent with a 1912 text | `raw/deu-luther1912.osis.xml` | `5df33f4bf3e086b6490b467cf8ddbf4cf95126b2826efaddf17b223ddd07f92b` | osis | 1189 / 30048 | 64 | 1922604 | English names only (64 flags) |
| `ita` | Italian | Italian | `title` "**Riveduta 1990**", `identifier` IRV_1990 — VETTED.txt claims "Riveduta 1927" | Protestant | 🔴 **EXPLICIT COPYRIGHT IN THE SOURCE:** `<rights>1990 Italian Riveduta Version / Copyright (c) 1990 / Societa Biblica Britiannica &amp; Forestriera, Rome, Italy</rights>`. **NOT redistributable.** Web-confirmed Oct 4: the same edition is catalogued as "© Libreria Sacre Scritture Roma 1990, ISBN 88-237-1051-0", and Società Biblica in'Italia's own history dates the Riveduta revisions as 1924 (Luzzi) → 1995/1996 (with Ginevra) → 2006. **Actionable:** the **1927 Riveduta** (`ItaRive`, e.g. SWORD) is a genuinely different, PD-eligible edition (Italy life+70 ⇒ 1998; US pre-1931 ⇒ PD since 2026). Swapping the 1990 file for a 1927 source clears this language. | `raw/ita-riveduta.osis.xml` | `e0b5c35ad8c2edfc76cbc4d988f67e7b702c9214e538426b5c5f01b33da1df20` | osis | 1189 / 29979 | 61 | 1963461 | ① **Rights block (C3 violated).** ② `sanitize` applied **17,945 mojibake repairs + 52 stray delimiters** — the text is damaged. ③ English names. VETTED.txt's version label is wrong; re-vet from scratch |
| `bul` | Bulgarian | Bulgarian | `title` "**Veren's Contemporary Bible**", `identifier` BulVeren — description: "This is an **updated** version of the Bible, published by Konstantin Fotinov, Petko Slaveykov and Hristodul Sichan-Nikolov in 1871. **This version is made by Veren LTD**", encoded 2010 | Protestant-ish | 🟠 **Commercial modern revision** by Veren LTD (`bible.netbg.com`, Free Bible Software). No `<rights>` element; PD status doubtful | `raw/bul-bulgarian.osis.xml` | `94c23830ec3fa343836f55c0ba84ccd98fec7f0dc7379cf1a53940f7e628c4b8` | osis | 1189 / 29978 | 61 | 2087167 | ① **Rights: modern commercial work, not the 1871 text VETTED.txt approved.** ② English names. Largest payload of the Latin set (12 MiB) |
| `fra` | French | French | `title` "**La Bible J.F. Ostervald 1996**", `identifier` ostv1996 — description: revised from Olivétan 1535, first published 1744, "version révisée en 1996" | Reformed | 🔴 `<rights>Public Domain</rights>` is the *packager's* assertion and is **contradicted by French law**: CPI art. **L.112-3** (as amended by PL 95-103 implementing TRIPS, adopted 14 May 1996) — "Les auteurs de traductions, d'adaptations, transformations ou arrangements des oeuvres de l'esprit jouissent de la protection instituée par le présent code" — reinforced by Berne Art. 7(3). A **1996 revision** is a transformation with its own protection, even over a PD 1744 base. (No French case-law citation confirmed for a *revision of an existing translation*, so this is a statute-based call, not settled case law.) | `raw/fra-ostervald.osis.xml` | `5a69ce3e1c4ab6b69dd6d21b74c6891afb1882c531d0fec416438d4aee674d52` | osis | 1189 / 30049 | 62 | 1976729 | ① Rights decision: ship 1996 or find an 1887 Ostervald. ② English names |
| `fin` | Finnish | Finnish | `title` "**Finish Version**" (sic); description: "PYHŽ RAAMATTU **(C) 1933, 1938** / Vanha Testamentti XI 1933 Uusi Testamentti XII 1938" | Evangelical Lutheran | 🔴 **EXPLICIT `(C) 1933, 1938`** in the source description, and **1938 is still in copyright in the US** — US Copyright Office Circular 15A: "all works published … before January 1, 1931, are in the public domain"; Circular 15T: works published after that date "could still be protected". So PD at home (Finland/EU life+70 ⇒ 2009) but **not** US-safe. No `<rights>` element. Nexus ships worldwide ⇒ treat as blocked. | `raw/fin-biblia.osis.xml` | `3d3bde765bc3af995356ac8b70453c72df26cdedbbc80948eca2b0b08fa19fe7` | osis | **1190** / 29983 | 79 | 1955852 | ① **Rights: explicit © + pre-1931 in the US.** ② **1190 chapters** vs KJV 1189. ③ 79 flags = worst parse in the set. ④ English names |
| `hun` | Hungarian | Hungarian | `title` "**Hungarian Version**", `identifier` hun, **description is empty** — "Karoli 1590" appears **only in the filename** | Reformed | No `<rights>` element; no description at all. PD assumed from lineage | `raw/hun-karoli.osis.xml` | `91f9b0c1447d96400a1cc0e7200eb37f74570b323a71ee16c497d681cd55b863` | osis | 1189 / 30047 | 63 | 2011519 | English names; **version unverified in-file**; 63 flags |
| `kor` | Korean | Korean | `title` "**Korean Version**", `identifier` kor, **description is empty** — the version **cannot be identified from the file**. `raw/` also holds `KorRV-osis.json` (11.8 MB, *Catholic* — excluded by C2) and `KorHKJV-osis.json` (13.2 MB) | unknown — possibly Catholic | 🟠 No `<rights>`, no description. If this turns out to be RV it is **Catholic and must be rejected outright**; Korean Revised (1961) is not pre-1929, so PD is unproven either way | `raw/kor-korean.osis.xml` | `ea64979f802469e62b3f3792bb8b01204c4448a4683a699be9cb08b715ebd01a` | osis | **1171** / 29520 | 64 | 1673373 | ① **C2 RISK: version unidentified — resolve before anything else.** ② **1171 chapters, 18 short of KJV** → adjudication needed. ③ English names. ④ Hangul wrap defect + font map (§7) |
| `sqi` | Albanian | Albanian | `title` "**Albanian Version**", `identifier` alb1, description "Albanian" — **no year anywhere** | Protestant | `<rights>I think public domain</rights>` — non-authoritative self-assessment by the packager | `raw/sqi-albanian.osis.xml` | `b37ec38022101493bb887ec1bbedd4e19225e763a2f766f11c4b511d48db5e62` | osis | 1189 / 29979 | 61 | 1997366 | English names; rights evidence is hearsay; no edition year |
| `swe` | Swedish | Swedish | `title` "**Swedish 1917 Version**", `identifier` SVD — description: "the official Swedish translation of **1917**, authorized by the throne for use in the Church of Sweden" | Lutheran | `<rights>i think public domain</rights>` | `raw/swe-swedish.osis.xml` | `13cff7f085410d0c4bb6fdc2105354ce5d22abc82153d977c09d56708335c977` | osis | 1189 / 30025 | 70 | 1992334 | **17 `unfilled_gap` disclosures — the only build with gaps**: JOS 21:36-37, NEH 7:68, MAT 17:21, 18:11, 21:44, 23:14, MRK 7:16, 9:44, 9:46, 11:26, 15:28, JHN 5:4, ACT 8:37, 15:34, 24:7, ROM 16:24. `gen-exalted-reds.py` will ABORT if any resolve to empty text. English names |
| `mri` | Maori | Maori | `title` "**Maori Version**", `identifier` MAO — description: "Maori Bible prepared by **Timothy Mora**. Text reproduced by Dr. Cleve Barlow." **No year** | Protestant | `<rights>i think public domain</rights>` | `raw/mri-maori.osis.xml` | `13e3afad708a95cd2b3193c2d6c7bf43dba79f9b6dea3db64988d8a849ce23a5` | osis | 1189 / 29979 | 61 | 1848760 | English names; rights evidence is hearsay; no edition year |
| `tgl` | Tagalog | Tagalog | `title` "**Ang Dating Biblia**", `identifier` TlgAngBiblia, publisher "Theologische Initiative Freiburg" — description: "**Philippines Bible Society (1905)**, Tagalog (Philippines National Language)" | Evangelical | ✅ `<rights>This Bible is now Public Domain.</rights>` — the strongest in-file assertion in the set, and the metadata is specific (1905, named publisher) | `raw/tgl-tagalog.osis.xml` | `c7567b9c234392d3538a889775412335e0ff5b04c18ebd237722eb6ffe37709d` | osis | 1189 / 29979 | 61 | 2003379 | **English names are the only blocker** — the strongest rights case in the set |
| `tha` | Thai | Thai | `title` "**KJV-Thai**", `identifier` kjvthai, **publisher is literally "Your Organisation"**, `<rights>` holds a reference to thaipope.org (no year) | Protestant (translated from KJV) | 🟠 **Provenance unverifiable** — placeholder publisher, no edition year | `raw/tha-thai.osis.xml` | `cf784c08e8059b16f6ab3da2433c8fc62a73c3f3d5772fffbb5be7778214cd2a` | osis | 1189 / 29979 | 61 | 2397871 | ① Rights/provenance. ② English names. ③ **Worst non-Latin layout numbers** (§7): 20.5 MiB, 254-column lines, 8 514 unbroken segments |
| `pol` | Polish | Polish | JSON source is `{"books":[…]}` with **per-chapter English names** ("Genesis 1") and **no module-level metadata**; the year evidence (1632/1738/1838/1881) + `<rights>I think public domain</rights>` live in the **sibling** `raw/pol-gdanska.osis.xml` | Protestant | Rights as above (sibling file); the build's own source carries no rights metadata | `raw/PolUGdanska-osis.json` | `d1d5d3d4c3d54c7307cfceda8b26be223eb9e7c7643512a8830bd9f8991aee0d` | sjson | 1189 / 31102 | 0 | 0 | 1479711 | ① **The source itself lists the books in English** — 48/66 identical to KJV, so no converter can fix it without a Polish heading list. ② **VETTED.txt names the wrong file** (`pol-gdanska.osis.xml`; the build uses `PolUGdanska-osis.json`). ③ Text itself is the most complete of the set (31102 verses) |

---

## 5. VETTED-NOT-BUILT

**None.** Every `BUILD` row in `bible-sources/VETTED.txt` has a
`bible-sources/build/<lang>/` directory with a `build-report.json`. Two build
directories are **not** languages and must not be packaged:

| dir | what it is |
|---|---|
| `bible-sources/build/polug/` | duplicate of `build/pol`, same source file |
| `bible-sources/build/ita-clean/` | duplicate of `build/ita`, same source file, same `sanitize` counters |

### Named in the plan but not yet vetted (no source file on disk)

`ja` (Shinkaiyaku 1970 — user has 66 PDFs locally), `ar` (Van Dyck),
`uk`, and Turkish (a source exists but is **rejected**, see §6). Also note the
plan's §4 lists Korean RV / ACF / CEI / NBS / Einheitsübersetzung / RSV-CE as
**excluded by C2** — they must never enter `VETTED.txt`.

---

## 6. REJECTED — reasons as recorded

| code | Source on disk | sha256 (raw) | Declared title | Recorded reason (VETTED.txt) |
|---|---|---|---|---|
| `dan` | `raw/dan-danish.osis.xml` | `5fab8f8dc8c790f472fa22e0afdba38cbeab8f59ea407758cb24fed7be58a129` | Danish Version | **REJECT incomplete — 61 of 66 books.** Shipping a Bible with holes is worse than not shipping |
| `nor` | `raw/nor-norwegian.osis.xml` | `fca2ef0d7e7c18e685f370693e2715c341092497288386b8f867e9c17b459160` | Norwegian Version | **REJECT incomplete — 64 of 66** |
| `tur` | `raw/tur-turkish.osis.xml` | `49786dd07665386dccc5b0a3ab1ab81ed6d1cb5f846ca5979f68e119d1a65c3e` | Turkish (`<publisher>nobody</publisher>`) | **REJECT incomplete — 65 of 66** |
| `lav` | `raw/lav-latvian.osis.xml` | `dfe09b42d0342efcaaf349c38455602f31ee9a113e2189155878eb338ba1492d` | Lativian Version | **REJECT incomplete — 27 of 66** |
| `swa` | `raw/swa-swahili.osis.xml` | `1ed6bdb2291d711d838b574ff6c2647cc897d9b766a510ba72d869038e5316ab` | Swahili NT | **REJECT incomplete — 26 of 66.** NT-only in practice |
| `hrv` | `raw/hrv-croatian.osis.xml` | `1ddd5d28217157e1d52d8afd5aff7cdbfe5c3bb137c6f404b2982db70ec93820` | Croatian Bible Version (1988) | **REJECT Catholic** (C2) — 73 books incl. deuterocanon, and 1988 ⇒ copyright |
| `heb` | `raw/heb-leningrad.usfx.xml` | `f621019959ac16bed4708edc3ac87418f56d30814380d2488a579c395011b687` | (none) | **REJECT OT-only** (38 books) **+ morphologically analysed** — morpheme slashes and glued words destroy readability. Separately blocked on font/RTL: `docs/MULTILINGUAL-PLAN.md` §5.4 |
| `lat` | ⚠ **file not on disk** | — | Clementine Vulgate | **REJECT Catholic** (C2). The rejection is recorded but the source is absent, so the verdict is **not re-verifiable from disk** — restore or delete the row |

Also excluded by user directive, never to be ingested: Portuguese **ACF** and
**ARC** (kept preserved on disk, never shipped).

---

## 7. Non-Latin scripts — what is actually blocked

Measured on the Oct 4 scratch builds (`WRAP = 88`, `gen-exalted-reds.py:23`;
wrapping splits on whitespace at `:86`/`:91` and counts **code points** at
`:107`/`:111`). `Site.reds:375` and `:443` split the chapter body on `{~}` and
render **each generated line as exactly one display row** — there is no
re-wrap in the reader, so the generator's wrap budget is the only wrapping
mechanism that exists.

| language | max line (display columns) | median | lines over 88 cols | unbroken lines (no break point) |
|---|---|---|---|---|
| `por` (Latin) | 88 | 80 | 0.0 % | 0 |
| `ron` (Latin + diacritics) | 88 | 80 | 0.0 % | 0 |
| `rus` (Cyrillic) | 93 | 76 | 0.3 % | 0 |
| `kor` (Hangul) | **159** | **139** | **70.9 %** | 0 |
| `chi` (CJK) | **210** | 64 | **22.4 %** | **51** |
| `tha` (Thai, no interword spaces) | **254** | 66 | 8.3 % | **8 514** |

Two independent, blocking defects:

1. **The wrap budget is code points, not display columns.** Hangul and CJK
   glyphs are double-width, so an "88-character" line renders up to ~176–210
   columns and overflows the canvas. This is a systematic ~2× overflow for
   *every* full-width script, independent of any per-language wrapping rule.
2. **The break rule is whitespace-only.** Thai and Chinese have few or no
   interword spaces, so whole verses become single unbroken tokens (8 514 Thai
   segments, 51 Chinese segments) that cannot wrap at all.

Fixing (1) and (2) means editing `scripts/gen-exalted-reds.py`, which is
**another agent's file** — not touched here.

Third, separate blocker — **font family selection, now with a solved
availability question.** `internet/EXALTED/Site.reds:175` hardcodes
`SetFontFamily("base\\gameplay\\gui\\fonts\\raj\\raj.inkfontfamily")` (Rajdhani,
a Latin display face), so every non-Latin build would render tofu.

✅ **`docs/FONT-ROUTE.md` (font owner, Oct 4) has already settled whether the
glyphs exist: they do.** The game ships foreign ink font families for
Cyrillic (`foreign\russian\raj_rus`), Hangul (`foreign\korean\kbiz_go`,
`nanum_square`), Han Simplified (`foreign\chinese\jing_xi_heig`), Han
Traditional (`foreign\chinese_traditional\ar_fang_xing_run_yuan`,
`jing_xi_heig_b5`) and Thai (`foreign\thai\th_sarabun_new`, `printable4u`).
Hebrew is the **only** hard "no shipped family" case — and `heb` is already
REJECTED in §6 anyway.

So the remaining font work is **route A from that doc**: a per-language
`SetFontFamily()` map in `Site.reds` (or language detection), estimated there as
low effort/risk with **no font assets redistributed**. That is a *site-owner*
change. Read `docs/FONT-ROUTE.md` before re-deriving any of this — it also
flags Thai combining-mark shaping and Cyrillic/Hangul metrics as still
in-game-unverified.

Keep the two apart: **fonts are a `Site.reds` fix; the wrap-width defect above
is a `gen-exalted-reds.py` fix.** Neither doc touches the other, and shipping a
language needs both.

---

## 8. How to add a new language

### 8a. If a `bible-sources/build/<lang>/` already exists (17 of 19 rows)

```bash
cd ~/cyberpunk-exalted
LANG=por
SRC=~/bible-sources/build/$LANG
SITE=~/exalted-lang-scratch/site-$LANG      # never inside the repo; /tmp gets wiped
OUT=~/exalted-lang-scratch/out              # never dist/ — the lead ships

# 1. site tree = the English Site.reds + a fresh generated data/ payload
mkdir -p "$SITE" && cp internet/EXALTED/Site.reds "$SITE/"

# 2. counts MUST come from that build, not from the KJV defaults —
#    chapters and verses differ per version (rus 1192/31352, kor 1171/29520,
#    fin 1190/29983, chi 31100, por 31098), and red-letter is always 0.
CH=$(python3 -c "import json;print(sum(b['chapters'] for b in json.load(open('$SRC/books.json'))))")
VS=$(python3 -c "import json;print(sum(b['verses']   for b in json.load(open('$SRC/books.json'))))")

python3 scripts/gen-exalted-reds.py \
    --src "$SRC" --book-subdir "" \
    --out "$SITE/data" \
    --expect-books 66 --expect-chapters "$CH" --expect-verses "$VS" --expect-red 0

# 3. package into a scratch dir — the slug gate runs and fails loudly
EXALTED_DIST="$OUT" EXALTED_SITE_SRC="$SITE" EXALTED_LANG_TAG=$LANG EXALTED_SKIP_CET=1 \
    bash scripts/package.sh
```

Expected: `slug gate ok [$LANG]: 66 books, 66 unique ASCII slugs, all canonical KJV`.

### 8b. If no build exists yet

```bash
python3 scripts/convert_bible.py --help          # owned by the converter agent
# then add a row to ~/bible-sources/VETTED.txt with the sha256, and repeat 8a.
```

Non-negotiable gates before a language may be packaged (not "nice to have"):

1. **Slugs** — `books.json` `short` must equal the canonical KJV
   `short` for the same book number. `scripts/package.sh` enforces this and
   aborts the build. Never "fix" this by transliterating.
2. **No empty verses** — `gen-exalted-reds.py` aborts on any; `swe`'s 17
   `unfilled_gap` disclosures are the live example.
3. **Native book names** — `build-report.json` `native_names` must be 66 and
   `english_name_fallback` empty. **13 builds fail this today**: the 12 OSIS
   ones resolve 0 headings, and `pol`'s source lists the books in English.
   ⚠ `native_names: 66` alone is NOT proof — `pol` reports 66 while emitting
   English names. Diff the names against `cet/EXALTED/data/books.json`.
4. **Counts passed explicitly** — never rely on the generator's KJV defaults.
5. **Rights** — a decision recorded in this file, not an assumption.
6. **`Site.reds` chrome** stays English until a per-language UI exists.

### 8c. Shipping (lead only)

Artifact lands in `dist/EXALTED_Terminal_77-Browser-<lang>-<ver>.zip` +
`.sha256`, then byte-identical copies to
`installer-usb/nexus-upload/EXALTED-Terminal-77/` and the ToolBox drive, with
localized `INSTALL-…` + `DESCRIPTION-…` text. Update `docs/CREDITS.md`
licensing and this file. **Never commit Bible source data into the public
repo.**

---

## 9. Evidence index — how to re-verify every claim above

```bash
# tallies + per-language build facts (native names, flags, disclosures)
python3 - <<'EOF'
import json,os
for d in sorted(os.listdir(os.path.expanduser('~/bible-sources/build'))):
    p=os.path.expanduser(f'~/bible-sources/build/{d}/build-report.json')
    if not os.path.isfile(p): continue
    r=json.load(open(p))
    print(f"{d:9} {r.get('format'):8} ch={r.get('total_chapters')} v={r.get('total_verses')} "
          f"native={r.get('native_names')} fallback={len(r.get('english_name_fallback') or [])} "
          f"flags={len(r.get('flags') or [])} disc={len(r.get('disclosure') or [])} "
          f"sanitize={r.get('sanitize')}")
EOF

# rights statements as they actually appear in the sources
grep -l '<rights>' ~/bible-sources/raw/*.xml | while read -r f; do
  printf '%s: ' "$(basename "$f")"; sed -n 's/.*<rights>\(.*\)<\/rights>.*/\1/p' "$f" | head -c 200; echo
done

# slug gate must pass for the shipped English tree
EXALTED_DIST=/tmp/x bash scripts/package.sh && echo "gate ok"

# English tree regenerates byte-identical (67 files)
python3 scripts/gen-exalted-reds.py --out /var/home/Gigatone/eng-regen
diff -rq internet/EXALTED/data /var/home/Gigatone/eng-regen && echo IDENTICAL
```

Note: `dist/*.zip.sha256` is **not reproducible from a rebuild** — Info-ZIP 3.0
stamps entry mtimes, so a rebuild of identical content yields a different zip
hash. Compare entry *content*, not zip bytes, when checking reproducibility.

English canonical data: `cet/EXALTED/data/books.json` — 66 books / 1189
chapters / 31 102 verses, keys per book are exactly
`n, name, short, chapters, verses`. **It carries no red-letter field**;
red-letter marking lives one level down, as `segs[]` on individual verses in
`cet/EXALTED/data/kjv/1..66.json` (2 028 of 31 102 verses have `segs[]`, which
is exactly what the shipped `ExaltedRedTotal() -> Int32 { return 2028; }`
reports; 3 407 `{r}…{/r}` runs render in the 66 shipped browser modules).
English raw source on the side-vault: `bible-sources/raw/eng-kjv.osis.xml`
sha256 `eeeae647fc28360ce47f9c0d5cc3b397b7fdd9913fe53dc9f44eb6deee50e253`
(not currently used by the build; the shipped English JSON is the canonical
in-repo data).

⚠ **Romanian `ron` was REMOVED 2026-10-06** (user order). The RCCV 2013
source was unattested (2013 electronic revision, corrections unknown) and was
never shipped. `translations/ron/` was purged from this repo's history and the
raw/build/site trees were deleted; the vetting record + hashes remain in
`bible-sources/VETTED.txt`. Do not re-add Romanian until an attested PD source
is obtained.
`translations/es/` is current and matches the shipped `-es` artifact.