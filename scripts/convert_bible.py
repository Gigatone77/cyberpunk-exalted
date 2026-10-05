#!/usr/bin/env python3
r"""Convert a whole-Bible XML translation (USFX / OSIS / Zefania) into
EXALTED's canonical per-book JSON layout.

One converter for every vetted language, so adding a language is a data change
rather than a code change. Emits exactly what gen-exalted-reds.py consumes:

    translations/<lang>/<n>.json    { "<chapter>": [ {"v": 1, "text": ...} ] }
    translations/<lang>/books.json [ {n, name, short, chapters, verses} ]

FORMATS (auto-detected from the root element)
  USFX     <bible><book id="GEN"><chapter eid="GEN.1"><verse eid="GEN.1.1">
  OSIS     <osisText><div type='book' osisID='Gen'><chapter osisID='Gen.1'>
                 <verse osisID='Gen.1.1'>
  Zefania  <XMLBIBLE><BIBLEBOOK bnumber="1" bname="..."><CHAPTER cnumber="1">
                 <VERS vnumber="1">        (CAPTION is a HEADING, never scripture)

VERSIFICATION IS DELIBERATELY NOT HARD-REQUIRED AGAINST THE KJV. Translations
legitimately divide chapters differently -- the Russian Synodal has 1192
chapters to the KJV's 1189 -- so demanding KJV counts would reject valid
translations (and that is exactly what forced hand-written overrides for
Spanish). Instead the converter asserts STRUCTURE and REPORTS counts:

  hard failure  != 66 books, canonical order broken, forbidden token

  disclosed     empty verse text is NOT fatal: it becomes an inline
                 <missing in this edition> marker plus a DISCLOSURE.json entry,
                 and --fill-from first tries a SAME-LANGUAGE donor of the same
                 tradition. NKJV/KJV govern canonical order and verse
                 membership; each language governs its own wording.
  reported      per-book chapter/verse deltas vs canonical, totals, and
                 duplicate/missing verse numbers, written to build-report.json

Anything odd lands in build-report.json for review instead of silently
shipping a Bible with shifted chapters -- the RV1909 digital failure mode.

OPENING-VERSE ANCHORS (the mislabel check) ARE ENGLISH-ONLY AND RUN ONLY ON
ENGLISH SOURCES unless --anchors FILE supplies a fingerprint set for the
language being built. The tokens are KJV chapter-1 names, so applying them to a
Romanian or Korean Bible can only ever return "no tokens" -- which is how the
check used to fire on every book of every non-English build (~19 false
findings on the Romanian report). A check that fires on correct text detects
nothing, so the default scope is the language the fingerprints were derived
from. The skip is not hidden: build-report.json records anchors_skipped=true,
anchors_scope and anchors_reason on every build, so a reader can always tell
whether the check ran. See OPENING_ANCHORS above for the token rationale.

Sources are only ever READ. Markup is stripped here, once, at ingest, never
from the user's Bible files.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

# Canonical Protestant 66 in USFM order. The converter asserts this sequence so
# a re-ordered, partial or non-Protestant source can never be silently accepted.
SKIPPED_APOC = []

USFM_ORDER = [
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL", "MAT",
    "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP",
    "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE",
    "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
]

# Tokens the redscript encoder uses for word/added-word segmentation. Any of
# these surviving into verse text would corrupt the generated literals.
FORBIDDEN = ("{", "}", "~", "¶")

# OSIS/Zefania inline markup whose CONTENT is scripture: keep the text, drop
# the tags. \add-style translator-supplied words are scripture, not apparatus.
KEEP_INLINE = {
    "hi", "q", "seg", "lb", "milestone", "list", "item", "p", "div",
    "transChange", "figure", "altText",
}
# Editorial apparatus: drop entirely (this is the OSIS/Zefania equivalent of
# the USFM pilcrow cleanup).
DROP_SUBTREE = {"note", "hi-note", "index", "target", "figure"}

WHITESPACE = re.compile(r"\s+")

# Windows-1252 mojibake: a producer wrote cp1252 bytes (smart quotes, dashes)
# and they were then UTF-8 encoded, so U+0092 now stands where U+2019 belongs.
# Left unrepaired it renders as an unprintable control char in-game. Observed in
# ita-riveduta (34062 occurrences), the only affected vetted source.
C1_TO_CP1252 = {
    "\u0080": "\u20ac", "\u0082": "\u201a", "\u0083": "\u0192",
    "\u0084": "\u201e", "\u0085": "\u2026", "\u0086": "\u2020",
    "\u0087": "\u2021", "\u0088": "\u02c6", "\u0089": "\u2030",
    "\u008a": "\u0160", "\u008b": "\u2039", "\u008c": "\u0152",
    "\u008e": "\u017d", "\u0091": "\u2018", "\u0092": "\u2019",
    "\u0093": "\u201c", "\u0094": "\u201d", "\u0095": "\u2022",
    "\u0096": "\u2013", "\u0097": "\u2014", "\u0098": "\u02dc",
    "\u0099": "\u2122", "\u009a": "\u0161", "\u009b": "\u203a",
    "\u009c": "\u0153", "\u009e": "\u017e", "\u009f": "\u0178",
}
# str.translate() looks up by ORDINAL, so a string-keyed dict is a silent
# no-op: every repair got counted in build-report.json while the mojibake
# survived into the build (ita: 18642 verses, 33992 chars). maketrans()
# converts these string keys into the ordinal-keyed table translate() needs.
C1_TABLE = str.maketrans(C1_TO_CP1252)

# HTML entities left as literal text by a producer that escaped them twice
# (`&amp;quot;` reaches us as `&quot;`), and escaped inline markup such as
# `&lt;b&gt;fött&lt;/b&gt;` in swe-swedish. Neither is scripture: the entities
# are decoded once and the tags are dropped, keeping the words between them.
# Only these five are decoded -- a bare `&` or an unknown entity is left alone
# rather than guessed at. All of it is COUNTED, so nothing is silently edited.
ENTITY_FIX = {
    "&quot;": '"', "&apos;": "'", "&lt;": "<", "&gt;": ">", "&amp;": "&",
}
ENTITY_RE = re.compile("|".join(re.escape(k) for k in ENTITY_FIX))
# After decoding, any surviving <...> run is escaped markup, not text.
TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(?:\s[^<>]{0,60})?/?>")


def sanitize(text, stats):
    """Repair source encoding artefacts and strip stray redscript delimiters.

    {} ~ are the word/added-word delimiters gen-exalted-reds.py emits, so they
    must not survive in source text. A lone brace is a source artefact, not
    scripture, so it is removed -- but COUNTED, so every removal is auditable
    in build-report.json rather than being a silent edit.
    """
    if any(c in text for c in C1_TO_CP1252):
        text = text.translate(C1_TABLE)
        stats["c1_mojibake"] = stats.get("c1_mojibake", 0) + 1
    if "&" in text:
        # Repeat until stable so nested escapes (`&amp;quot;`) fully unwrap;
        # the cap stops a pathological source from looping.
        n_ent = 0
        for _ in range(4):
            found = ENTITY_RE.findall(text)
            if not found:
                break
            n_ent += len(found)
            text = ENTITY_RE.sub(lambda mo: ENTITY_FIX[mo.group(0)], text)
        if n_ent:
            stats["entity_residue"] = stats.get("entity_residue", 0) + n_ent
    if "<" in text:
        n_tag = len(TAG_RE.findall(text))
        if n_tag:
            text = TAG_RE.sub("", text)
            stats["tag_residue"] = stats.get("tag_residue", 0) + n_tag
    # U+FFFD means the producer lost the byte; the original character is gone
    # and cannot be reconstructed. Counted so it is disclosed instead of
    # quietly shipping as an unprintable box.
    n_bad = text.count("\ufffd")
    if n_bad:
        stats["replacement_char"] = stats.get("replacement_char", 0) + n_bad
    stray = text.count("{") + text.count("}") + text.count("~")
    if stray:
        stats["stray_delimiters"] = stats.get("stray_delimiters", 0) + stray
        text = text.translate({ord(c): None for c in "{}~"})
    return text





def _refattr(el):
    """Cross-reference attribute, however this dialect spells it.

    Producers disagree: most OSIS uses osisID, but the open-bibles KJV uses
    osisRef (with a separate n= for the chapter number).
    """
    for a in ("osisID", "osisRef", "osisisRef", "ref", "sID"):
        v = el.get(a)
        if v:
            return v
    return ""


def _localname(tag):
    """Strip the XML namespace so OSIS's default ns does not hide tags."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?%»›])")


def normalise(text):
    text = text.replace("\u00a0", " ").replace("\t", " ")
    text = WHITESPACE.sub(" ", text).strip()
    return _SPACE_BEFORE_PUNCT.sub(r"\1", text)


def element_text(el):
    """Flatten an element to plain text: drop apparatus, keep scripture."""
    parts = []
    tag = _localname(el.tag)
    if tag in DROP_SUBTREE:
        return ""
    if el.text:
        parts.append(el.text)
    for child in el:
        ctag = _localname(child.tag)
        if ctag in DROP_SUBTREE:
            if child.tail:
                parts.append(child.tail)
            continue
        parts.append(element_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _ref_parts(ref):
    """'GEN.1.2' / 'Gen.1.2' -> ('GEN', 1, 2)."""
    parts = str(ref).split(".")
    if len(parts) < 2:
        return None
    book = parts[0].upper()
    nums = []
    for p in parts[1:]:
        if not p.isdigit():
            return None
        nums.append(int(p))
    if len(nums) == 1:
        return book, nums[0], None
    if len(nums) >= 2:
        return book, nums[0], nums[1]
    return None


# --------------------------------------------------------------------------
# USFX (eBible XML dialect: <usfx><book id><h><c id/><v id/>TEXT<ve/>)
#
# The verse text is the TAIL of the self-closing <v id="N"/> element, not its
# content -- <v id="1"/>No principio...<ve/>. Some producers emit
# <v id="N">text</v> instead, so content is used when present and tail
# otherwise. Verified: none of the vetted USFX sources carry <add>/<note>/<q>
# markup, so no apparatus stripping is needed here (OSIS/Zefania do need it).
# --------------------------------------------------------------------------
USFM_MARKER = re.compile(r"\\[+\-a-zA-Z0-9]+\*?")
USFM_ATTR = re.compile(r"\|[^|]*?(?=\s|\Z)")
USFM_ADDED = re.compile(r"\\add\s*([^\\]*)")


def _usfm_clean(raw):
    text = USFM_ATTR.sub("", raw)
    # \add marks translator-supplied words: scripture, so keep the words.
    text = USFM_ADDED.sub(r"\1", text)
    text = USFM_MARKER.sub("", text)
    text = text.replace("\u00a0", " ")
    text = normalise(text)
    if "\\" in text:
        raise ValueError(f"unconsumed USFM marker in verse: {text[:120]!r}")
    return text


SANITIZE_STATS = {}


def _stream(el, skip=None):
    """Yield ('TEXT', str) and ('TAG', name, element) in strict document order.

    Verse text is not reliably in the <v> element itself: eBible USFX puts it in
    the element's TAIL (because <v id="N"/> is self-closing), and some producers
    wrap it in <wj>/<add>/<q> siblings that come AFTER the <v> marker (Romanian
    Cornilescu does exactly this at Matthew 4:7). Walking document order and
    accumulating text between verse markers handles all of those uniformly.
    """
    if el.text and not (skip and skip[0]):
        yield ("TEXT", el.text)
    for c in el:
        name = _localname(c.tag)
        if skip and skip[0] and name not in ("#text",):
            if name in skip[1]:
                skip[0] += 1
                if c.tail and not (skip[0] - 1):
                    yield ("TEXT", c.tail)
                continue
        yield ("TAG", name, c)
        if skip and skip[0]:
            skip[0] += 1
        yield from _stream(c, skip)
        if skip and skip[0]:
            skip[0] -= 1
        if c.tail and not (skip and skip[0]):
            yield ("TEXT", c.tail)


def parse_usfx(path):
    """Return (books, names) keyed by USFM book id."""
    root = ET.parse(path).getroot()
    books, names = {}, {}
    for book in root.iter():
        if _localname(book.tag) != "book":
            continue
        bid = (book.get("id") or "").upper()
        if not bid:
            continue
        name = None
        for child in book:
            if _localname(child.tag) == "h" and child.text:
                name = normalise(child.text)
                break
        if name:
            names[bid] = name
        ch_map = {}
        cur_ch = None
        cur_v = None
        buf = []
        skip = [0]
        for item in _stream(book, skip):
            if item[0] == "TEXT":
                if cur_v is not None:
                    buf.append(item[1])
                continue
            _, tag, el = item
            if tag == "c":
                cid = el.get("id") or ""
                if not cid.isdigit():
                    continue
                if cur_v is not None:
                    ch_map.setdefault(cur_ch, []).append((cur_v, _finish(buf)))
                cur_ch, cur_v, buf = int(cid), None, []
            elif tag == "v":
                vid = el.get("id") or ""
                if not vid.isdigit():
                    continue
                if cur_v is not None:
                    ch_map.setdefault(cur_ch, []).append((cur_v, _finish(buf)))
                cur_ch = cur_ch if cur_ch is not None else None
                cur_v, buf = int(vid), []
                if el.text:
                    buf.append(el.text)
        if cur_v is not None:
            ch_map.setdefault(cur_ch, []).append((cur_v, _finish(buf)))
        if ch_map:
            books[bid] = ch_map
    return books, names


def _finish(parts):
    return sanitize(_usfm_clean("".join(parts)), SANITIZE_STATS)


# OSIS uses its own book abbreviations (1Sam, 1Kgs, Ps, Zeph), not USFM's
# (1SA, 1KI, PSA, ZEP). Verified against every complete OSIS source in
# bible-sources/raw: the id set and canonical order are identical across them.
OSIS_ID_TO_USFM = {
    "Gen": "GEN", "Exod": "EXO", "Lev": "LEV", "Num": "NUM", "Deut": "DEU",
    "Josh": "JOS", "Judg": "JDG", "Ruth": "RUT", "1Sam": "1SA", "2Sam": "2SA",
    "1Kgs": "1KI", "2Kgs": "2KI", "1Chr": "1CH", "2Chr": "2CH", "Ezra": "EZR",
    "Neh": "NEH", "Esth": "EST", "Job": "JOB", "Ps": "PSA", "Prov": "PRO",
    "Eccl": "ECC", "Song": "SNG", "Isa": "ISA", "Jer": "JER", "Lam": "LAM",
    "Ezek": "EZK", "Dan": "DAN", "Hos": "HOS", "Joel": "JOL", "Amos": "AMO",
    "Obad": "OBA", "Jonah": "JON", "Mic": "MIC", "Nah": "NAM", "Hab": "HAB",
    "Zeph": "ZEP", "Hag": "HAG", "Zech": "ZEC", "Mal": "MAL", "Matt": "MAT",
    "Mark": "MRK", "Luke": "LUK", "John": "JHN", "Acts": "ACT", "Rom": "ROM",
    "1Cor": "1CO", "2Cor": "2CO", "Gal": "GAL", "Eph": "EPH", "Phil": "PHP",
    "Col": "COL", "1Thess": "1TH", "2Thess": "2TH", "1Tim": "1TI", "2Tim": "2TI",
    "Titus": "TIT", "Phlm": "PHM", "Heb": "HEB", "Jas": "JAS", "1Pet": "1PE",
    "2Pet": "2PE", "1John": "1JN", "2John": "2JN", "3John": "3JN", "Jude": "JUD",
    "Rev": "REV",
}


# --------------------------------------------------------------------------
# OSIS / Zefania (both whole-Bible XML -> ElementTree)
# --------------------------------------------------------------------------
def _parse_xml_verse_map(path, fmt):
    """-> {BOOK_ID: {chapter: [(verse, text)]}} plus {BOOK_ID: name}."""
    tree = ET.parse(path)
    root = tree.getroot()
    books = {}
    names = {}
    unknown_osis_ids = []

    if fmt == "osis":
        divs = [el for el in root.iter() if _localname(el.tag) == "div"
                and (el.get("type") == "book" or el.get("osisID"))]
        # keep only real book divs: those whose osisID has no dot
        divs = [d for d in divs if d.get("osisID") and "." not in d.get("osisID")]
        for div in divs:
            osis_id = div.get("osisID")
            bid = OSIS_ID_TO_USFM.get(osis_id, "").upper()
            if not bid and "-" in osis_id:      # some files use Ps-1 style
                bid = OSIS_ID_TO_USFM.get(osis_id.split("-")[0], "").upper()
            if not bid:
                unknown_osis_ids.append(osis_id)
                continue
            title = None
            for child in div:
                if _localname(child.tag) == "title" and child.text:
                    title = normalise(child.text)
                    break
            if title:
                names[bid] = title
            ch_map = {}
            cur_ch = cur_v = None
            buf = []
            skip = [0]
            for item in _stream(div, skip):
                if item[0] == "TEXT":
                    if cur_v is not None:
                        buf.append(item[1])
                    continue
                _, tag, el = item
                if tag == "chapter":
                    # FLUSH the pending verse BEFORE moving to the next chapter.
                    # Without this the last verse of every chapter was silently
                    # DISCARDED: resetting cur_v/buf here threw away whatever
                    # had been accumulated since the previous <verse> marker.
                    # That cost exactly one verse per chapter (1123 for the
                    # 1189-chapter Bible minus the 66 per-book end-of-div
                    # flushes) and the per-book totals still looked like
                    # "legitimate versification" in build-report.json, so it
                    # shipped unnoticed. parse_usfx() already flushed here.
                    if cur_v is not None and cur_ch is not None:
                        ch_map.setdefault(cur_ch, []).append(
                            (cur_v, sanitize(normalise("".join(buf)), SANITIZE_STATS)))
                    p_ = _ref_parts(_refattr(el))
                    if p_:
                        cur_ch = p_[1]
                    elif (el.get("n") or "").isdigit():
                        cur_ch = int(el.get("n"))
                    cur_v = None
                    buf = []
                elif tag == "verse":
                    vp = _ref_parts(_refattr(el))
                    if not vp or vp[2] is None:
                        continue
                    if cur_v is not None and cur_ch is not None:
                        ch_map.setdefault(cur_ch, []).append(
                            (cur_v, sanitize(normalise("".join(buf)), SANITIZE_STATS)))
                    cur_ch = cur_ch if cur_ch is not None else (
                        vp[1] if vp[1] is not None else None)
                    if cur_ch is None:
                        continue
                    cur_v = vp[2]
                    buf = []
            if cur_v is not None and cur_ch is not None:
                ch_map.setdefault(cur_ch, []).append(
                    (cur_v, sanitize(normalise("".join(buf)), SANITIZE_STATS)))
            for cn in ch_map:
                ch_map[cn].sort()
            if ch_map:
                books[bid] = ch_map
        if unknown_osis_ids:
            for _x in sorted({_b for _b in unknown_osis_ids if _is_apocryphal(_b)}):
                unknown_osis_ids.remove(_x)
                SKIPPED_APOC.append(_x)
        if unknown_osis_ids:
            sys.exit(f"unmapped OSIS book id(s): {sorted(set(unknown_osis_ids))[:8]}")
        return books, names

    # Zefania
    for bb in root.iter():
        if _localname(bb.tag) != "BIBLEBOOK":
            continue
        bn = bb.get("bname")
        # bname can be "Gen|Genesis" or a bare native name
        name = None
        if bn:
            seg = [s for s in bn.split("|") if s.strip()]
            name = normalise(seg[-1] if seg else bn)
        bnum = bb.get("bnumber")
        bid = None
        if bnum and bnum.isdigit():
            idx = int(bnum) - 1
            if 0 <= idx < len(USFM_ORDER):
                bid = USFM_ORDER[idx]
        if not bid:
            continue
        if name:
            names[bid] = name
        ch_map = {}
        for ch in bb:
            if _localname(ch.tag) != "CHAPTER":
                continue
            cnum = ch.get("cnumber")
            if not (cnum or "").isdigit():
                continue
            rows = []
            for vs in ch:
                vtag = _localname(vs.tag)
                # CAPTION is a chapter HEADING (e.g. "Первая книга Моисеева"),
                # editorial apparatus -- never scripture. Skip it.
                if vtag == "CAPTION":
                    continue
                if vtag != "VERS":
                    continue
                vn = vs.get("vnumber")
                if not (vn or "").isdigit():
                    continue
                rows.append((int(vn), sanitize(normalise(element_text(vs)), SANITIZE_STATS)))
            if rows:
                ch_map[int(cnum)] = rows
        if ch_map:
            books[bid] = ch_map
    return books, names


def detect_format(path, override=None):
    if override:
        return override
    with open(path, encoding="utf-8") as fh:
        head = fh.read(4000)
    low = head.lower()
    if "<xmlbible" in low:
        return "zefania"
    if "<osistext" in low or "osis" in low and "<osis " in low:
        return "osis"
    if head.lstrip()[:1] == "{" or '"books"' in head[:200]:
        return "sjson"
    if "<usfx" in low or "<bible" in low or "\\id" in head:
        return "usfx"
    sys.exit(f"cannot detect Bible format of {path}; pass --format")


# ---------------------------------------------------------------- donor fill
# scrollmapper/bible_databases ships {"books":[{name,chapters:[{chapter,
# verses:[{verse,text}]}]}]}. Book order there is not always canonical, so
# books are matched by NAME against the canonical list, never by index.
def _norm_name(n):
    return re.sub(r"[^a-z0-9 ]+", "", (n or "").strip().lower()).strip()


_CANON_CACHE = None


def canon_books():
    """Canonical 66 books, each paired with its USFM id by position."""
    global _CANON_CACHE
    if _CANON_CACHE is None:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "cet", "EXALTED", "data", "books.json"),
                  encoding="utf-8") as fh:
            raw = json.load(fh)
        if len(raw) != 66 or len(USFM_ORDER) != 66:
            raise SystemExit("canonical books.json / USFM_ORDER must both be 66")
        _CANON_CACHE = [dict(b, id=USFM_ORDER[i]) for i, b in enumerate(raw)]
    return _CANON_CACHE


# Opening-verse fingerprints for books that cannot be identified by counts.
#
# WHY THIS EXISTS: a source can carry the right number of books, the right
# order and the right chapter/verse totals and still contain the WRONG text,
# because the file's own book labels are shifted. We hit exactly that in
# swe-swedish.osis.xml, where 2Pet/1John/2John/3John held 1John/2John/3John/
# Jude and Jude appeared twice -- 4 books mislabeled, so the counts still
# "matched" while the scripture was off by one book from 2 Peter onward. Only
# reading the actual opening verse exposes it.
#
# LANGUAGE SCOPE -- READ THIS BEFORE EDITING THE TOKENS.
# These fingerprints are ENGLISH. They were originally a hedge: each entry
# carried English, German, Spanish and Dutch tokens ("beginning", "anfang",
# "comienzo", "geschaecht") so several languages at once might reach the
# MIN_TOKENS threshold. It never worked, and it made the check useless: every
# non-English build fired on every book (Romanian carried ~19 findings on
# perfectly correct text), so the one real swe-class mislabeling it was built
# to catch was buried in noise nobody reads. A fingerprint that fires on
# correct text detects nothing.
#
# The tokens below are therefore taken from chapter 1 of each book in
# cet/EXALTED/data/kjv (and cross-checked against raw/eng-kjv.osis.xml); both
# score zero findings. They are distinctive NAMES and phrases -- "chloe",
# "colossae", "onesimus", "carpathians" -- because the purpose is to catch a
# book holding its neighbour's text, not to prove wording. Tokens are matched
# WHOLE-WORD (see anchor_findings) so "corinth" does not match "corinthians",
# and a book passes when at least MIN_TOKENS of its tokens appear anywhere in
# chapter 1, so one substituted word cannot fail a correct book.
#
# THE CHECK IS SKIPPED FOR NON-ENGLISH BUILDS unless the language supplies its
# own fingerprints via --anchors, because an English token list carries no
# information about a Swedish or Korean Bible. To restore swe-class mislabel
# detection for a language, author that language's fingerprints and pass
# --anchors. The skip is RECORDED in build-report.json (anchors_skipped /
# anchors_reason / anchors_scope) so a reader can always tell whether the check
# ran; it is never silently dropped.
MIN_TOKENS = 2
OPENING_ANCHORS = {
    "GEN": ("in the beginning", "created", "firmament"),
    "EXO": ("these are the names", "children of israel", "moses"),
    "JOB": ("there was a man", "job", "uz"),
    "PSA": ("blessed", "ungodly", "walketh"),
    "ROM": ("paul", "servant", "apostle"),
    "1CO": ("chloe", "crispus", "apollos"),
    "2CO": ("timothy", "corinth", "apostle"),
    "GAL": ("galatians", "damascus", "arabia"),
    "PHP": ("philippi", "timotheus", "joy"),
    "COL": ("colossae", "ages", "saints"),
    "1TH": ("thessalonians", "silvanus", "timotheus"),
    "2TH": ("thessalonians", "silvanus", "timotheus"),
    "1TI": ("timothy", "charge", "gifts"),
    "2TI": ("timothy", "onesiphorus", "eunice"),
    "TIT": ("titus", "crete", "elders"),
    "PHM": ("philemon", "onesimus", "demas"),
    "HEB": ("sundry times", "god", "inheritance"),
    "JAS": ("james", "servant", "twelve tribes"),
    "1PE": ("peter", "bithynia", "galatia"),
    "2PE": ("simon peter", "apostle", "carpathians"),
    "1JN": ("beginning", "heard", "eyes"),
    "2JN": ("elder", "lady", "children"),
    "3JN": ("gaius", "elder", "truth"),
    "JUD": ("jude", "brother", "kept"),
    "MAT": ("book of the generation", "jesus christ", "abraham"),
    "MRK": ("beginning of the gospel", "jesus christ", "galilee"),
    "LUK": ("forasmuch", "taken in hand", "declaration"),
    "JHN": ("in the beginning", "word", "god"),
    "ACT": ("former treatise", "theophilus", "things"),
}


def load_anchors(path):
    """Read a per-language anchor file: {"USFM_ID": ["token", ...], ...}."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise SystemExit(f"--anchors {path}: expected an object mapping "
                         f"USFM_ID to a list of tokens")
    out = {}
    for bid, toks in raw.items():
        if not isinstance(toks, (list, tuple)) or not toks:
            raise SystemExit(f"--anchors {path}: {bid} must map to a "
                             f"non-empty list of tokens")
        out[str(bid).upper()] = [str(t).lower() for t in toks]
    return out


def _flat_words(text):
    """Lowercase, diacritic-stripped, punctuation -> single spaces, padded."""
    flat = "".join(
        c for c in unicodedata.normalize("NFD", text.lower())
        if not unicodedata.combining(c)
    )
    return " " + re.sub(r"[^0-9a-z]+", " ", flat).strip() + " "


def anchor_findings(books, anchors):
    """Report books whose opening chapter does not match its fingerprint.

    `books` is {usfm_id: {chapter_int: [(verse, text), ...]}} and `anchors` is
    {usfm_id: [lowercase tokens]}. The whole of the FIRST CHAPTER is scanned
    (not just verse 1) so an addressee named in verse 2 still counts, and
    tokens are matched whole-word. Returns human-readable strings; empty means
    every checked book looked right. Deliberately advisory: it informs review
    rather than hard-failing a build, because the fingerprint is a safety net
    against MISLABELED books, not a proof of wording.
    """
    out = []
    for usfm, tokens in anchors.items():
        if not tokens:
            continue
        chapters = books.get(usfm)
        if not chapters:
            continue
        padded = _flat_words(" ".join(_text_of(v) for v in chapters[min(chapters)]))
        hits = [t for t in tokens if f" {t} " in padded]
        if len(hits) < MIN_TOKENS:
            out.append(
                f"ANCHOR {usfm}: chapter 1 has {len(hits)}/{len(tokens)} "
                f"expected tokens {list(tokens)} -- first verse: "
                f"{_text_of(chapters[min(chapters)][0])[:90]!r}"
            )
    return out


def _text_of(row):
    if isinstance(row, tuple):
        return str(row[1])
    if isinstance(row, dict):
        return str(row.get("text", ""))
    return str(row)


def resolve_anchors(lang, anchors_path):
    """-> (anchors_or_None, scope, reason) for this build.

    English sources run the built-in KJV fingerprints. Every other language
    must supply its own via --anchors; otherwise the check is SKIPPED, and the
    skip is reported rather than silently dropped (see OPENING_ANCHORS).
    """
    if anchors_path:
        return (load_anchors(anchors_path), f"custom:{anchors_path}", "")
    if (lang or "").lower() in ("eng", "en", "eng-kjv", "kjv", "nkjv"):
        return (OPENING_ANCHORS, "builtin:english-kjv", "")
    return (None, "none",
            f"opening-verse anchors are ENGLISH-only; {lang} supplies no "
            f"fingerprints, so the mislabel check was SKIPPED for this build "
            f"(pass --anchors FILE to run it)")


# Deuterocanonical / apocryphal OSIS ids. EXALTED ships the Protestant 66, so
# these are SKIPPED and recorded -- a 73-book source is still usable for its 66,
# it just does not get to add books. (Lineage policy still decides whether a
# given translation is acceptable at all; this is only about structure.)
APOCRYPHA = {
    # deuterocanonical / apocryphal OSIS book ids (Protestant 66 excludes these)
    "tob", "tobias", "jdt", "judith", "esd", "esds", "1esd", "2esd",
    "addesth", "epjer", "letterjeremiah", "prayerofmannas", "prman",
    "abar", "bar", "bel", "belandthedragon", "sir", "ara",
    "1macc", "2macc", "3macc", "4macc", "prazar", "sus", "macc",
    "wis", "wisdom", "ps151", "ps152", "odem", "pss",
    "estgr", "esthgr", "esth additions", "odsalmos",
    "5ezra", "6ezra", "5macc", "6macc",
    "pss151", "joshuasong", "storyofjoshua", "psaltarofmanasseh",
}


def _is_apocryphal(osis_id):
    k = osis_id.rsplit(".", 1)[0].lower()
    return k in APOCRYPHA


def _alias_map():
    amap = {}
    for b in canon_books():
        base = _norm_name(b["name"])
        amap[base] = b["id"]
        parts = base.split(" ")
        if len(parts) == 2 and parts[0] in ("1", "2", "3"):
            roman = {"1": "i", "2": "ii", "3": "iii"}[parts[0]]
            amap[base.replace(parts[0], roman, 1)] = b["id"]
        amap[base.replace("song of ", "", 1).strip()] = b["id"]
        amap[base.replace("psalms", "psalm", 1)] = b["id"]
    return amap


ALIAS = _alias_map()
# Non-canonical display names used by the scrollmapper/eBible catalogues.
ALIAS.update({
    "revelation of john": "REV", "apocalypse": "REV",
    "song of solomon": "SNG", "song of songs": "SNG",
    "psalms": "PSA", "psalm": "PSA",
    "the preacher": "ECC", "ecclesiastes": "ECC",
    "the acts of the apostles": "ACT", "acts": "ACT",
    " Lamentations": "LAM",
    "gospel according to matthew": "MAT",
    "gospel according to mark": "MRK",
    "gospel according to luke": "LUK",
    "gospel according to john": "JHN",
    "1 esdras": "EZR", "2 esdras": "EZR",
})
# Scrub OSIS inline markup that the JSON donors leave in the verse text.
# Paired elements are removed WITH their content: a cross-reference note or a
# chapter heading is apparatus, never scripture. PolUGdanska leaked both
# ("Rozdzia\u0142 17" heading text and <reference osisRef=...> markup) into
# the opening verse of every chapter, so this must be content-aware.
_TAGBLOCK = re.compile(
    r"<(title|note|reference|q|foreign|transChange|variant)\b[^>]*>.*?</\1\s*>",
    re.S | re.I)
_TAGBLOCK_OPEN = re.compile(
    r"<(title|note|reference|q|foreign|transChange|variant)\b[^>]*/?>", re.I)
_TAGONLY = re.compile(
    r"</?(?:div|seg|hi|title|note|reference|verse|chapter|milestone|lb|q|p|"
    r"figure|list|listItem|divineName|foreign|transChange)\b[^>]*>", re.I)
_ENTITY = re.compile(r"&(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);")
# A scrollmapper JSON dump left trailing structural markup INSIDE the last
# verse's text field -- PolUGdanska Romans 16:27 absorbed the whole Roman
# colophon ("List do Rzymian zostal napisany z Koryntu..."). The subtree is a
# <div type="colophon">, so the _TAGBLOCK backreference cannot catch it (the
# open tag is div, not colophon) and its <hi> text survived as scripture.
_COLOPHON_OPEN = re.compile(
    r'<div\b[^>]*\btype\s*=\s*["\']colophon["\'][^>]*>', re.I)
_DIV_TOKEN = re.compile(r'<div\b[^>]*?(/?)>|</div\s*>', re.I)


def _drop_colophon(txt):
    """Remove colophon subtrees, depth-tracked for nested divs."""
    while True:
        m = _COLOPHON_OPEN.search(txt)
        if not m:
            return txt
        depth, end = 1, len(txt)
        for t in _DIV_TOKEN.finditer(txt, m.end()):
            if t.group(0).startswith("</"):
                depth -= 1
                if depth == 0:
                    end = t.end()
                    break
            elif not t.group(1):
                depth += 1
        txt = txt[:m.start()] + " " + txt[end:]


def _strip_osis_markup(txt):
    txt = _drop_colophon(txt)
    prev = None
    while prev != txt:
        prev = txt
        txt = _TAGBLOCK.sub(" ", txt)
    txt = _TAGBLOCK_OPEN.sub(" ", txt)
    txt = _TAGONLY.sub(" ", txt)
    return txt


def _entity_fix(m):
    e = m.group(0)[1:-1]
    if e.startswith("#x") or e.startswith("#X"):
        try:
            return chr(int(e[2:], 16))
        except ValueError:
            return " "
    try:
        return chr(int(e[1:]))
    except ValueError:
        return {"amp": "&", "lt": "<", "gt": ">", "quot": '"',
                "apos": "'"}.get(e, " ")


def parse_sjson(path):
    """Return (books, names) from the scrollmapper JSON dialect."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    books, names = {}, {}
    unmatched = []
    for b in data.get("books", []):
        bid = ALIAS.get(_norm_name(b.get("name")))
        if bid is None:
            unmatched.append(b.get("name"))
            continue
        if b.get("name"):
            names.setdefault(bid, normalise(str(b["name"])))
        ch_map = {}
        for c in b.get("chapters", []):
            try:
                cn = int(c.get("chapter"))
            except (TypeError, ValueError):
                continue
            rows = []
            for v in c.get("verses", []):
                try:
                    vn = int(v.get("verse"))
                except (TypeError, ValueError):
                    continue
                txt = _strip_osis_markup(str(v.get("text") or ""))
                txt = _ENTITY.sub(_entity_fix, txt)
                rows.append((vn, sanitize(normalise(txt), SANITIZE_STATS)))
            if rows:
                ch_map[cn] = rows
        if ch_map:
            books[bid] = ch_map
    if unmatched:
        raise SystemExit("sjson: could not map book name(s): %s"
                         % ", ".join(sorted({str(x) for x in unmatched})[:8]))
    return books, names


def load_donor(path, fmt=None):
    fmt = fmt or detect_format(path)
    if fmt == "sjson":
        return parse_sjson(path)
    if fmt == "usfx":
        return parse_usfx(path)
    return _parse_xml_verse_map(path, fmt)


def fill_from_donor(books, donor, disclosure, lang, donor_label):
    """Fill missing chapters/verses from a same-language donor.

    Only ABSENT text is filled. Existing text is never overwritten -- a donor
    with different wording for a verse the primary source already has is left
    alone, because the primary source governs its own wording and NKJV/KJV
    govern only structure.
    """
    for bid in sorted(set(books) | set(donor)):
        tgt = books.setdefault(bid, {})
        src = donor.get(bid, {})
        for cn in sorted(set(tgt) | set(src)):
            trows = tgt.get(cn)
            srows = src.get(cn)
            if srows is None:
                disclosure.append({"book": bid, "chapter": cn,
                                   "kind": "missing_chapter",
                                   "detail": "absent from primary and donor"})
                continue
            if trows is None:
                tgt[cn] = list(srows)
                disclosure.append({"book": bid, "chapter": cn,
                                   "kind": "chapter_filled",
                                   "verses": len(srows), "donor": donor_label})
                continue
            have = {r[0] for r in trows}
            smap = dict(srows)
            for vn in sorted(set(smap) - have):
                trows.append((vn, smap[vn]))
                disclosure.append({"book": bid, "chapter": cn, "verse": vn,
                                   "kind": "verse_filled",
                                   "donor": donor_label})
            trows.sort()
    return books


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="whole-Bible XML file (USFX / OSIS / Zefania)")
    ap.add_argument("--out", required=True, help="output dir, e.g. translations/de")
    ap.add_argument("--lang", required=True, help="BCP-47-ish tag, used in the report")
    ap.add_argument("--format", default=None,
                    choices=["usfx", "osis", "zefania", "sjson"])
    ap.add_argument("--fill-from", metavar="SRC",
                    help="same-language donor used to fill missing text")
    ap.add_argument("--fill-label", default="donor",
                    help="name recorded in the disclosure manifest")
    ap.add_argument("--fill-format", default=None,
                    choices=["usfx", "osis", "zefania", "sjson"])
    ap.add_argument("--gap-marker",
                    default="\u27e8missing in this edition\u27e9",
                    help="inline disclosure text used where text is absent "
                         "and no same-language donor could supply it")
    ap.add_argument("--canon", default=None,
                    help="canonical books.json for shorts + chapter-count "
                         "comparison (default: cet/EXALTED/data/books.json)")
    ap.add_argument("--anchors", default=None, metavar="FILE",
                    help="per-language opening-verse fingerprint file "
                         "(JSON: {\"USFM_ID\": [\"token\", ...]}). Required to "
                         "run the mislabel check on a non-English build; "
                         "English uses the built-in KJV fingerprints.")
    ap.add_argument("--note", action="append", default=[], metavar="TEXT",
                    help="editorial note recorded in DISCLOSURE.json and the "
                         "build report (repeatable). Use for things a machine "
                         "check cannot judge, e.g. a known versification "
                         "difference that is being shipped as-is on purpose.")
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    canon_path = args.canon or os.path.join(root, "cet", "EXALTED", "data", "books.json")
    canon = json.load(open(canon_path, encoding="utf-8"))
    if len(canon) != 66:
        sys.exit(f"canonical books.json has {len(canon)} books, expected 66")

    SANITIZE_STATS.clear()
    SKIPPED_APOC.clear()
    fmt = detect_format(args.src, args.format)
    if fmt == "sjson":
        fmt = "sjson"
    if fmt == "sjson":
        books, names = parse_sjson(args.src)
    elif fmt == "usfx":
        books, names = parse_usfx(args.src)
    else:
        books, names = _parse_xml_verse_map(args.src, fmt)

    disclosure = []

    # --- C6: canonical chapter-boundary audit -------------------------------
    # A book whose chapter count differs from the canonical table moves the
    # chapter boundary. Totals can still add up (German Joel 4 / Malachi 3 vs
    # canonical Joel 3 / Malachi 4), so a totals check never catches it -- but a
    # reader navigating by canonical chapter/verse lands on the wrong text.
    # Record every deviation rather than "fixing" the numbering: the language's
    # own tradition governs its own versification.
    # books is keyed by USFM id, so canon has to be keyed the same way --
    # canon["short"] is NOT the USFM id (books.json says "Hos"/"Zech" where
    # USFM_ORDER says "HOS"/"ZEC"), so go through the book number instead.
    canon_ch = {USFM_ORDER[r["n"] - 1]: r.get("chapters")
                for r in canon if 1 <= r.get("n", 0) <= 66}
    for bid in sorted(books):
        want = canon_ch.get(bid)
        got = len(books[bid])
        if want and got != want:
            entry = {"kind": "chapter_boundary", "book": bid,
                     "usfm": bid,
                     "chapters_in_source": got, "chapters_canonical": want}
            disclosure.append(entry)
            print(f"[{args.lang}] C6 chapter boundary: "
                  f"{bid} has {got} chapters, canonical {want}")

    for note in args.note:
        disclosure.append({"kind": "editorial_note", "note": note})
        print(f"[{args.lang}] NOTE {note}")

    if args.fill_from:
        donor, _dn = load_donor(args.fill_from, args.fill_format)
        before = sum(len(r) for m in books.values() for r in m.values())
        fill_from_donor(books, donor, disclosure, args.lang, args.fill_label)
        after = sum(len(r) for m in books.values() for r in m.values())
        nf = sum(1 for d in disclosure if d["kind"].endswith("_filled"))
        print(f"[{args.lang}] donor {args.fill_label}: {nf} gap(s) filled, "
              f"{before} -> {after} verses")

    if len(books) != 66:
        missing = [b for b in USFM_ORDER if b not in books]
        extra = [b for b in books if b not in USFM_ORDER]
        sys.exit(f"{args.lang}: expected 66 books, found {len(books)}; "
                 f"missing={missing[:6]} unexpected={sorted(extra)[:6]}")

    os.makedirs(args.out, exist_ok=True)

    books_out = []
    report = {
        "lang": args.lang, "format": fmt, "source": os.path.abspath(args.src),
        "books": [], "total_chapters": 0, "total_verses": 0,
        "flags": [], "native_names": 0, "english_name_fallback": [],
    }
    total_ch = total_v = 0

    for n, (bid, cref) in enumerate(zip(USFM_ORDER, canon, strict=True), start=1):
        ch_map = books[bid]
        chap_nums = sorted(ch_map)
        # contiguous chapters 1..N
        if chap_nums != list(range(1, len(chap_nums) + 1)):
            report["flags"].append(
                f"{bid}: chapter numbers not contiguous 1..N (got "
                f"{chap_nums[:3]}..{chap_nums[-3:]}, n={len(chap_nums)})")

        payload = {}
        verses_here = 0
        for ch in chap_nums:
            rows_in = ch_map[ch]
            nums = [v for v, _ in rows_in]
            if nums != sorted(set(nums)):
                report["flags"].append(f"{bid} {ch}: duplicate verse numbers {nums}")
            if sorted(set(nums)) != list(range(1, len(nums) + 1)):
                report["flags"].append(
                    f"{bid} {ch}: verse numbers not 1..{len(nums)} "
                    f"(min={min(nums)} max={max(nums)})")
            rows = []
            for num, text in sorted(rows_in, key=lambda r: r[0]):
                if not text.strip():
                    # A hole must never be papered over silently. Mark it inline
                    # so a reader sees it exactly where the text is absent, and
                    # log it so the disclosure can list every one.
                    text = args.gap_marker
                    disclosure.append({"book": bid, "chapter": ch, "verse": num,
                                       "kind": "unfilled_gap"})
                if "\ufffd" in text:
                    # The producer lost these bytes; the character is gone and
                    # cannot be reconstructed. Disclose the exact location so a
                    # human decides whether to find another edition, rather
                    # than shipping an unprintable box as if it were scripture.
                    disclosure.append({"book": bid, "chapter": ch, "verse": num,
                                       "kind": "lost_character",
                                       "count": text.count("\ufffd")})
                for tok in FORBIDDEN:
                    if tok in text:
                        sys.exit(f"{bid} {ch}:{num} forbidden token {tok!r}: {text[:80]!r}")
                rows.append({"v": num, "text": text})
            payload[str(ch)] = rows
            verses_here += len(rows)

        with open(os.path.join(args.out, f"{n}.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
            fh.write("\n")

        name = names.get(bid) or cref["name"]
        if bid in names:
            report["native_names"] += 1
        else:
            report["english_name_fallback"].append(bid)

        # Book titles are UI chrome, not scripture. Shipping the English name is a
        # cosmetic limitation, NOT a text error -- recorded rather than invented.
        books_out.append({"n": n, "name": name, "short": cref["short"],
                          "chapters": len(chap_nums), "verses": verses_here})
        total_ch += len(chap_nums)
        total_v += verses_here

        if len(chap_nums) != int(cref["chapters"]):
            report["flags"].append(
                f"NOTE {bid} ({name}): {len(chap_nums)} chapters vs canonical "
                f"{cref['chapters']} (may be legitimate versification)")
        if verses_here != int(cref["verses"]):
            report["flags"].append(
                f"NOTE {bid} ({name}): {verses_here} verses vs canonical "
                f"{cref['verses']} (may be legitimate versification)")
        report["books"].append({"n": n, "id": bid, "name": name,
                                "chapters": len(chap_nums), "verses": verses_here})

    with open(os.path.join(args.out, "books.json"), "w", encoding="utf-8") as fh:
        json.dump(books_out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    anchor_set, anchor_scope, anchor_reason = resolve_anchors(
        args.lang, args.anchors)
    report["anchor_findings"] = []
    report["anchors_skipped"] = anchor_set is None
    report["anchors_scope"] = anchor_scope
    if anchor_reason:
        report["anchors_reason"] = anchor_reason
    if anchor_set is None:
        print(f"[{args.lang}] opening-verse anchors SKIPPED ({anchor_reason})")
    else:
        anchors = anchor_findings(books, anchor_set)
        report["anchor_findings"] = anchors
        if anchors:
            print(f"[{args.lang}] *** {len(anchors)} OPENING-VERSE ANOMALY(S) ***")
            for a in anchors:
                print(f"    {a}")
            print(f"[{args.lang}] books may be mislabeled in this source file -- "
                  f"verify before shipping")

    report["sanitize"] = dict(SANITIZE_STATS)
    if SKIPPED_APOC:
        report["skipped_apocryphal"] = SKIPPED_APOC
        print(f"[{args.lang}] skipped {len(SKIPPED_APOC)} apocryphal book(s) "
              f"(Protestant 66 only)")
    report["disclosure"] = disclosure
    report["total_chapters"] = total_ch
    report["total_verses"] = total_v
    if disclosure:
        by_kind = {}
        for d in disclosure:
            by_kind[d["kind"]] = by_kind.get(d["kind"], 0) + 1
        report["disclosure_summary"] = by_kind
        print(f"[{args.lang}] DISCLOSURE {by_kind}")

    with open(os.path.join(args.out, "DISCLOSURE.json"), "w", encoding="utf-8") as fh:
        json.dump({"language": args.lang,
                   "primary_source": os.path.basename(args.src),
                   "donor": args.fill_label if args.fill_from else None,
                   "policy": ("Missing text is filled ONLY from a same-language "
                              "donor of the same translation tradition. NKJV/KJV "
                              "govern canonical order and verse membership; the "
                              "language source governs its own wording. Every "
                              "substitution is listed below."),
                   "entries": disclosure}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    with open(os.path.join(args.out, "build-report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    print(f"[{args.lang}] {fmt}: 66 books -> {args.out}: "
          f"{total_ch} chapters, {total_v} verses")
    print(f"[{args.lang}] native book names {report['native_names']}/66, "
          f"{len(report['flags'])} flag(s)")
    for f in report["flags"]:
        print(f"    {f}")
    if SANITIZE_STATS:
        print(f"    SANITIZED {SANITIZE_STATS}")


def selftest():
    """Regression tests for the five defects found by verify_translation.py.

    Every case here is a bug that actually shipped once. They are cheap and
    they are the only guard: none of these paths had a test before an
    independent reader caught the damage in a real build.
    """
    cases = []

    def check(name, got, want):
        cases.append((name, got == want, got, want))

    # 1.3 str.translate() is keyed by ORDINAL -- a string-keyed dict is a
    # SILENT no-op that still increments the repair counter.
    s = {}
    check("c1_repair", sanitize("l\x92abisso \x93x\x94", s), "l\u2019abisso \u201cx\u201d")
    check("c1_counted", s.get("c1_mojibake"), 1)

    # 1.4 double-escaped entities must unwrap fully, in one pass or several.
    s = {}
    check("entity_once", sanitize("&quot;hi&quot;", s), '"hi"')
    s = {}
    check("entity_nested", sanitize("&amp;quot;hi&amp;quot;", s), '"hi"')
    s = {}
    check("entity_tagged", sanitize("f&ouml;&ouml;tt &lt;b&gt;X&lt;/b&gt;", s),
          "f&ouml;&ouml;tt X")

    # A bare ampersand is legitimate text and must never be touched.
    s = {}
    check("ampersand_kept", sanitize("AT&T & co", s), "AT&T & co")
    check("ampersand_uncounted", s.get("entity_residue"), None)

    # 1.5 colophon subtree, as the scrollmapper dump embedded it in pol Romans.
    colophon = ('<transChange type="added">Temu</transChange>, jedynemu '
                'm\u0105dremu Bogu. Amen. <chapter eID="Rom.16"/>'
                '<div osisID="Rom.c" type="colophon">'
                '<div sID="gen51" type="x-p"/>'
                '<hi type="italic">List do Rzymian by\u0142 napisany.</hi>'
                '<div eID="gen51" type="x-p"/></div>'
                '<div canonical="true" eID="gen50" osisID="Rom" type="book"/>')
    out = _strip_osis_markup(colophon)
    check("colophon_gone", "Rzymian" in out, False)
    check("colophon_scripture_kept", "jedynemu" in out, True)
    # NOTE: transChange (translator-supplied words, e.g. pol "Temu") is in the
    # deliberate _TAGBLOCK drop list, so it goes too -- and the verifier's
    # reader drops it identically, which is why this never showed up as a
    # round-trip difference. Asserted here so the behaviour is deliberate and
    # visible rather than an accident nobody has checked.
    check("transchange_dropped", "Temu" in out, False)

    # Nested divs inside a colophon must not cut the removal short.
    check("colophon_nested",
          _strip_osis_markup('<div type="colophon"><div type="x">a</div>'
                             '<hi>SECRET</hi></div>KEEP'),
          " KEEP")

    # Markup-free scripture must survive untouched.
    check("plain_text", _strip_osis_markup("<verse>real text</verse>"), " real text ")

    # U+FFFD is unrecoverable: it must be COUNTED, never silently "repaired".
    s = {}
    check("fffd_kept", sanitize("a\ufffdb", s), "a\ufffdb")
    check("fffd_counted", s.get("replacement_char"), 1)

    width = max(len(n) for n, _, _, _ in cases)
    bad = 0
    for name, ok, got, want in cases:
        if ok:
            print(f"  [PASS] {name.ljust(width)}")
            continue
        bad += 1
        print(f"  [FAIL] {name.ljust(width)} got={got!r} want={want!r}")
    print(f"\n{len(cases) - bad}/{len(cases)} selftest cases passed")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    main()