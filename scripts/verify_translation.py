#!/usr/bin/env python3
r"""INDEPENDENT verification of an EXALTED Bible translation build.

This is the check ON the converter, never a second copy of it. It re-parses
the raw source with its own streaming XML reader (expat token stream, not
ElementTree trees) and its own text normalisation, then holds the build
against that reference. No code is shared with convert_bible.py on purpose:
if both are wrong the same way, sharing the parser would hide it.

    verify_translation.py BUILD_DIR --source RAW [--format usfx|osis|zefania|sjson|auto]
                           [--canon PATH] [--json] [--verbose] [--top N]
    verify_translation.py --batch BUILD_ROOT        # every language dir under ROOT
    verify_translation.py --selftest                # prove each check fires

Exit codes
    0  clean
    1  hard failure (text does not match the source, structure broken,
       forbidden token shipped, undisclosed gap, wrong script, ...)
    2  warnings only (typically legitimate versification deltas vs the KJV)

WHAT IS CHECKED (ids used in --json output)
    doubled_text        verse text is an exact whole-string repeat (t[:k]+t[k:]),
                        plus the weaker "first 40 chars appear twice" signature
    roundtrip           EVERY verse compared against an independent parse of the
                        raw source; mismatches classified exact/ws/punct/doubled/
                        text/absent/extra.  This is the ground truth check and
                        is never skipped: no source => hard failure.
    forbidden_tokens    { } ~ ¶ backslash, C0/C1 controls, surviving XML entity
                        or angle-bracket markup in verse text
    structure           66 books, canonical USFM order, contiguous chapters and
                        verses, books.json metadata agreeing with the JSON
    short_slug          `short` builds NETdir:// URL segments: ASCII, non-empty,
                        no space/slash/backslash/colon, unique, stable vs canon
    gaps                empty verses and gap markers, reconciled BOTH ways
                        against DISCLOSURE.json (undisclosed gap = hard failure)
    encoding            C1 mojibake, U+FFFD, tripled CJK runs, combining piles
    script              dominant-script ratio per language + English-stopword
                        ratio + top non-ASCII word frequencies
    report_reconciliation  build-report.json / DISCLOSURE.json vs reality,
                        plus VETTED.txt provenance

READ-ONLY. Nothing outside --selftest's own temp dir is ever written, and no
Bible file anywhere is opened for writing, moved or re-encoded.
"""
from __future__ import annotations

import argparse
import collections
import fnmatch
import glob
import json
import os
import re
import shutil
import sys
import unicodedata
import xml.parsers.expat as expat

# --------------------------------------------------------------------------
# canonical shape
# --------------------------------------------------------------------------
USFM_ORDER = [
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL", "MAT",
    "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP",
    "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE",
    "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
]
USFM_INDEX = {b: i for i, b in enumerate(USFM_ORDER)}

# The redscript generator (gen-exalted-reds.py) uses these as delimiters for
# word / added-word segmentation; any survivor corrupts the generated literals.
FORBIDDEN_CHARS = ("{", "}", "~", "\u00b6", "\\")

# OSIS/Zefania element whose CONTENT is scripture (keep the text) ...
KEEP_CONTENT = {
    "q", "seg", "add", "p", "div", "list", "listItem", "item", "milestone",
    "lb", "transChange", "figure", "altText", "w", "lg", "l", "foreign",
    "divineName", "hi", "abbr", "sig", "sl", "pn", "k", "ord", "po", "cls",
    "li", "b", "i", "sc", "em", "bdo", "sup", "sub", "rtl", "ltr", "unclear",
}
# ... and element whose content is editorial apparatus (drop tag AND content).
# STRUCTURAL elements are deliberately absent: <book>, <c>, <v>, <chapter>,
# <verse>, <s>, <usfm>, <rem>, <toc>, <pb> carry verses or chapter structure and
# must never be dropped, only ignored.
DROP_CONTENT = {
    "note", "hi-note", "index", "target", "head", "title", "figure", "fig",
    "picture", "reference", "variant", "editor", "comment", "caption",
}
# Front/back matter whose text must never leak into a verse buffer.
DROP_USFX_EXTRA = {"ide", "id", "h", "ts", "categories", "mt", "toc", "rem"}
DROP_OSIS_EXTRA = {"header", "work", "revisionDesc", "category"}

# Windows-1252 mojibake: U+0080-U+009F standing where a cp1252 printable belongs.
# Applied to BOTH sides of the comparison so the check stays about text content,
# never about which encoding repair a tool chose. Reported separately.
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

ZERO_WIDTH = {ord(c): None for c in "\u200b\u200c\u200d\u2060\ufeff\u00ad\u202a\u202b\u202c"}

WS_RE = re.compile(r"\s+")
WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
ENTITY_RE = re.compile(r"&(?:[a-zA-Z]{2,10}|#\d{1,7}|#[xX][0-9a-fA-F]{1,6});")
ANGLE_TAG_RE = re.compile(r"</?[A-Za-z!?][A-Za-z0-9:_.-]*(?:\s[^<>]{0,80})?/?>")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7a3]")

# Gap markers: the converter's own (U+27E8 ... U+27E9), plus the shapes real
# sources use when a verse is absent from an edition.
GAP_PATTERNS = [
    re.compile("\u27e8[^\u27e9]{0,60}\u27e9"),
    re.compile(r"(?i)missing in this (?:edition|version|translation|printing)"),
    re.compile(r"(?i)<\s*[a-z]{0,8}[^<>]{0,20}missing[^<>]{0,20}>"),
    re.compile(r"(?i)\bpart missing\b"),
    re.compile(r"(?i)\b(?:verse )?(?:not available|not present|not in this)\b"),
    re.compile(r"(?i)^\s*(?:n\s*/?\s*a\.?|not available|no text)\s*$"),
    re.compile(r"^\s*(?:\.{3,}|\u2014|-)\s*$"),
]

# Languages whose letters must be precomposed (a decomposed build is a bug).
PRECOMPOSED = {"bul", "rus", "cze", "deu", "dut", "fin", "fra", "hun", "ita",
               "mri", "pol", "polug", "por", "ron", "sqi", "swe", "tgl", "es",
               "ita-clean"}
# Expected dominant script per language code.
LANG_SCRIPT = {
    "bul": "cyrl", "rus": "cyrl", "kor": "hangul", "chi": "han", "tha": "thai",
    "cze": "latin", "deu": "latin", "dut": "latin", "fin": "latin",
    "fra": "latin", "hun": "latin", "ita": "latin", "mri": "latin",
    "pol": "latin", "polug": "latin", "por": "latin", "ron": "latin",
    "sqi": "latin", "swe": "latin", "tgl": "latin", "es": "latin",
    "ita-clean": "latin", "heb": "hebr", "ell": "greek", "ara": "arab",
}
# Languages that should carry diacritics; ~0 means "fell back to ASCII English".
DIACRITIC_EXPECTED = {"ron", "pol", "polug", "cze", "hun", "sqi", "por",
                      "ita", "fra", "deu", "es"}
# Function words that are English and essentially no other vetted language.
ENGLISH_STOPWORDS = {
    "the", "and", "that", "was", "were", "with", "from", "have", "this",
    "they", "which", "their", "there", "would", "could", "about", "shall",
    "unto", "thou", "thy", "thee", "hath", "him", "them", "his", "her",
    "because", "behold", "wherein", "whosoever",
}
ENGLISH_UNTRANSLATED_THRESHOLD = 0.30

_SCRIPT_RANGES = (
    (0x0041, 0x024F, "latin"), (0x1E00, 0x1EFF, "latin"),
    (0x2C60, 0x2C7F, "latin"), (0xA720, 0xA7FF, "latin"),
    (0x0370, 0x03FF, "greek"), (0x1F00, 0x1FFF, "greek"),
    (0x0400, 0x04FF, "cyrl"), (0x0500, 0x052F, "cyrl"),
    (0x2DE0, 0x2DFF, "cyrl"), (0xA640, 0xA69F, "cyrl"),
    (0x0590, 0x05FF, "hebr"), (0xFB1D, 0xFB4F, "hebr"),
    (0x0600, 0x06FF, "arab"), (0x0750, 0x077F, "arab"),
    (0x0900, 0x097F, "deva"), (0x0E00, 0x0E7F, "thai"),
    (0x0E80, 0x0EFF, "thai"), (0x3040, 0x30FF, "kana"),
    (0xAC00, 0xD7A3, "hangul"), (0x1100, 0x11FF, "hangul"),
    (0x3130, 0x318F, "hangul"),
    (0x3400, 0x4DBF, "han"), (0x4E00, 0x9FFF, "han"),
    (0xF900, 0xFAFF, "han"),
)


def script_of(ch):
    """Dominant-script bucket for one character ('' for non-letters)."""
    o = ord(ch)
    for lo, hi, name in _SCRIPT_RANGES:
        if lo <= o <= hi:
            return name
    if ch.isalpha():
        return "other"
    return ""


# --------------------------------------------------------------------------
# text normalisation (comparison layer only -- never applied to any output)
# --------------------------------------------------------------------------
def norm_text(text):
    """Whitespace/encoding-level normalisation applied to BOTH sides."""
    if not text:
        return ""
    t = text.translate(C1_TO_CP1252).translate(ZERO_WIDTH)
    t = t.replace("\u00a0", " ").replace("\t", " ").replace("\r", " ")
    return WS_RE.sub(" ", t).strip()


_PUNCT_MAP = {}
for _a, _b in (("\u2018", "'"), ("\u2019", "'"), ("\u201a", "'"),
               ("\u201c", '"'), ("\u201d", '"'), ("\u201e", '"'),
               ("\u2013", "-"), ("\u2014", "-"), ("\u2212", "-"),
               ("\u00ab", '"'), ("\u00bb", '"'), ("\u2039", '"'),
               ("\u203a", '"'), ("\u02bc", "'"), ("\u00b7", "-")):
    _PUNCT_MAP[ord(_a)] = _b


def loose_key(text):
    """Case-, accent- and punctuation-insensitive key, for classifying near-misses."""
    t = norm_text(text)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.translate(_PUNCT_MAP).casefold()
    return "".join(c for c in t if c.isalnum())


def exact_double_split(t):
    """Return k if t == t[:k] + t[k:], else None.

    Equality of the two halves forces len(t)-k == k, so the only candidate split
    is the midpoint and the O(n^2) scan is unnecessary: k must be len(t)//2 and
    len(t) must be even. (Same result, provably, in O(n).)
    """
    n = len(t)
    if n < 4 or n % 2:
        return None
    h = n // 2
    return h if t[:h] == t[h:] else None


def repeat_prefix_split(t, width=40):
    """Weaker signature: the first `width` chars of t occur again inside t."""
    if len(t) <= width:
        return False
    return t.find(t[:width], 1) != -1


def is_doubled_ish(t):
    """True when t reads as its own first half repeated (exact or near-exact)."""
    k = exact_double_split(t)
    if k is not None:
        return True
    # A duplicate carries its own separator at the seam ("X Y X Y" vs "XXYY"),
    # so the length is odd and exact_double_split can never fire.  Comparing the
    # whitespace-stripped halves catches SHORT verses, which the width-40 prefix
    # probe below is too wide to notice.
    squashed = re.sub(r"\s+", "", t)
    if len(squashed) != len(t) and exact_double_split(squashed) is not None:
        return True
    head = norm_text(t)
    half = len(head) // 2
    if half < 8:
        return repeat_prefix_split(t)
    return head[:half].rstrip() == norm_text(head[half:])[:half].rstrip()


# --------------------------------------------------------------------------
# independent source parsers -- expat token stream, no ElementTree
# --------------------------------------------------------------------------
class SourceReader:
    """Streaming dialect reader.

    Subclasses implement start/close/chars. `drop` counts the nesting depth of
    apparatus subtrees whose content must be discarded; self-closing elements
    emit one start and one end, so the depth arithmetic stays balanced.
    """

    DROP = DROP_CONTENT

    def __init__(self):
        self.books = collections.defaultdict(dict)   # usfm -> {ch: [(v, text)]}
        self.names = {}                              # usfm -> source title
        self.extra = {}                              # usfm -> notes collected
        self.stats = collections.Counter()
        self.drop = 0
        self.buf = []

    # -- helpers ---------------------------------------------------------
    def _flush(self, chapter, verse):
        if verse is None or chapter is None:
            return
        text = self.clean("".join(self.buf))
        self.buf = []
        self.books[chapter[0]].setdefault(chapter[1], []).append((verse, text))

    def feed_text(self, chunk):
        if not self.drop:
            self.buf.append(chunk)

    def clean(self, text):
        return norm_text(text)

    # -- expat plumbing --------------------------------------------------
    def parse(self, path):
        p = expat.ParserCreate()
        try:
            p.buffer_text = True
        except AttributeError:                      # pragma: no cover
            pass
        p.StartElementHandler = self._start
        p.EndElementHandler = self._end
        p.CharacterDataHandler = self._chars
        with open(path, "rb") as fh:
            p.ParseFile(fh)
        self.finish()
        return self

    def _start(self, tag, attrs):
        name = tag.rsplit("}", 1)[-1] if "}" in tag else tag
        if self.drop:
            self.drop += 1
            return
        if name in self.DROP:
            self.drop = 1
            return
        self.start(name, attrs)

    def _end(self, tag):
        if self.drop:
            self.drop -= 1
            return
        name = tag.rsplit("}", 1)[-1] if "}" in tag else tag
        self.close(name)

    def _chars(self, data):
        self.feed_text(data)

    # -- to be provided by subclasses -----------------------------------
    def start(self, name, attrs):
        pass

    def close(self, name):
        pass

    def finish(self):
        pass

    # -- output ----------------------------------------------------------
    def sorted_books(self):
        out = {}
        for bid, chapters in self.books.items():
            out[bid] = {c: sorted(v) for c, v in sorted(chapters.items())}
        return out


def _ref_numbers(el):
    """Trailing numeric components of a ref, however the dialect spells it.

    OSIS refs are '<word><chapter>[.<verse>]', so the numbers are the LAST
    components, not the first: 'Gen.1.2' -> [1, 2].
    """
    for a in ("osisID", "osisRef", "osisref", "sID", "ref", "n"):
        v = el.get(a)
        if not v:
            continue
        parts = [p for p in str(v).split(".") if p != ""]
        nums = []
        while parts and parts[-1].isdigit():
            nums.insert(0, int(parts.pop()))
        if nums:
            return nums
    return []


class UsfxReader(SourceReader):
    """<usfx><book id><h><c id/><v id/>TEXT<ve/>  (text lives in the TAIL)."""

    DROP = DROP_CONTENT | DROP_USFX_EXTRA

    def __init__(self):
        super().__init__()
        self.book = None
        self.chapter = None
        self.verse = None
        self.in_h = False
        self.h_buf = []

    def start(self, name, attrs):
        if name == "book":
            self.book = (attrs.get("id") or "").upper() or None
            self.chapter = None
            self.verse = None
        elif name == "h":
            self.in_h = True
            self.h_buf = []
        elif name == "c":
            # <c id="1"/> is SELF-CLOSING in most USFX, so the last verse of the
            # previous chapter is still pending here -- flush it or it is lost.
            if self.verse is not None:
                self._flush(self.chapter, self.verse)
                self.verse = None
            self.buf = []
            raw = attrs.get("id") or attrs.get("s") or ""
            if raw.isdigit():
                self.chapter = (self.book, int(raw))
            elif "osisRef" in attrs or "ref" in attrs:
                nums = _ref_numbers(attrs)
                self.chapter = (self.book, nums[-1]) if nums else None
            else:
                self.chapter = (self.book, (self.chapter[1] + 1)
                                if self.chapter else None)
        elif name == "v":
            if self.verse is not None:
                self._flush(self.chapter, self.verse)
            raw = attrs.get("id") or ""
            if raw.isdigit():
                self.verse = int(raw)
            else:
                nums = _ref_numbers(attrs)
                self.verse = nums[-1] if nums else None
            self.buf = []
        elif name in ("q", "add", "wj", "sl", "sig", "pn", "k", "ord", "po",
                      "cls", "li", "sc", "em", "bdo", "sup", "sub", "no"):
            pass

    def close(self, name):
        if name == "h":
            self.in_h = False
            title = norm_text("".join(self.h_buf))
            if title and self.book:
                self.names[self.book] = title
        elif name == "book":
            if self.verse is not None:
                self._flush(self.chapter, self.verse)
                self.verse = None
            self.buf = []
        elif name == "c":
            if self.verse is not None:
                self._flush(self.chapter, self.verse)
                self.verse = None
            self.buf = []

    def _chars(self, data):
        if self.in_h:
            self.h_buf.append(data)
        elif self.verse is not None:
            self.buf.append(data)

    def feed_text(self, chunk):
        self._chars(chunk)

    def finish(self):
        if self.verse is not None:
            self._flush(self.chapter, self.verse)
            self.verse = None


class OsisReader(SourceReader):
    """<osisText><div type=book osisID=Gen><chapter><verse osisID=Gen.1.1>."""

    DROP = DROP_CONTENT | DROP_OSIS_EXTRA

    def __init__(self):
        super().__init__()
        self.book = None
        self.chapter = None
        self.verse = None
        self.depth = 0
        self.book_depth = None
        self.title_depth = None
        self.title_buf = []

    def start(self, name, attrs):
        if name == "div":
            ref = attrs.get("osisID") or attrs.get("osisRef") or ""
            if ref and "." not in ref and self.book_depth is None:
                self.book = self.map_book(ref)
                self.book_depth = self.depth
                self.chapter = None
                self.verse = None
            elif ref and self.book_depth is not None:
                # a nested <div> only re-states the chapter when its ref holds
                # exactly one number ('Gen.1'); 'Gen.1.1' is a verse ref.
                nums = _ref_numbers({"osisID": ref})
                if len(nums) == 1:
                    self.chapter = (self.book, nums[0])
                    self.verse = None
                    self.buf = []
            self.depth += 1
            return
        if name == "chapter":
            if self.book_depth is not None:
                nums = _ref_numbers(attrs)
                if nums:
                    self.chapter = (self.book, nums[-1])
                elif self.chapter is None:
                    self.stats["chapter_ref_without_number"] += 1
                self.verse = None
                self.buf = []
        elif name == "verse":
            if self.book_depth is None:
                # Outside every book div: count it, never drop it silently --
                # an unplaced verse is excluded from the round-trip comparison.
                self.stats["unplaced_verse"] += 1
                return
            if self.verse is not None:
                self._flush(self.chapter, self.verse)
            nums = _ref_numbers(attrs)
            if len(nums) >= 2:
                # 'Gen.1.2' -> chapter 1, verse 2.  This also repairs a <chapter>
                # whose own ref carried no number (e.g. 'Ps151').
                self.chapter = (self.book, nums[-2])
                self.verse = nums[-1]
            elif len(nums) == 1 and self.chapter is not None:
                self.verse = nums[0]
            else:
                self.verse = None
                self.stats["unplaced_verse"] += 1
            self.buf = []
            if "transChange" in (attrs.get("type") or ""):
                self.stats["transchange_attr"] += 1
        elif name == "transChange":
            self.stats["transchange"] += 1
        elif name == "title":
            if self.book_depth is not None and self.verse is None:
                self.title_depth = self.depth
                self.title_buf = []
        self.depth += 1

    def close(self, name):
        self.depth = max(0, self.depth - 1)
        if name == "title" and self.title_depth is not None:
            title = norm_text("".join(self.title_buf))
            if title and self.book:
                self.names.setdefault(self.book, title)
            self.title_depth = None
        elif name == "chapter":
            if self.verse is not None:
                self._flush(self.chapter, self.verse)
                self.verse = None
            self.buf = []
        elif name == "div":
            if self.book_depth is not None and self.depth <= self.book_depth:
                if self.verse is not None:
                    self._flush(self.chapter, self.verse)
                    self.verse = None
                self.book_depth = None
                self.chapter = None
                self.buf = []

    def _chars(self, data):
        if self.title_depth is not None:
            self.title_buf.append(data)
        elif self.verse is not None:
            self.buf.append(data)

    def feed_text(self, chunk):
        self._chars(chunk)

    def finish(self):
        if self.verse is not None:
            self._flush(self.chapter, self.verse)
            self.verse = None

    @staticmethod
    def map_book(ref):
        from_osis = _OSIS_ID_TO_USFM
        if ref in from_osis:
            return from_osis[ref]
        return ref.split("-")[0] if "-" in ref else ref


class ZefaniaReader(SourceReader):
    """<XMLBIBLE><BIBLEBOOK bnumber><CHAPTER cnumber><VERS vnumber>."""

    DROP = DROP_CONTENT | {"information"}

    def __init__(self):
        super().__init__()
        self.book = None
        self.chapter = None
        self.verse = None
        self.stack = []

    def start(self, name, attrs):
        self.stack.append(name)
        if name == "BIBLEBOOK":
            num = attrs.get("bnumber") or ""
            idx = int(num) - 1 if num.isdigit() else -1
            self.book = USFM_ORDER[idx] if 0 <= idx < 66 else None
            title = attrs.get("bname") or ""
            if title and self.book:
                seg = [s for s in title.split("|") if s.strip()]
                self.names[self.book] = norm_text(seg[-1])
            self.chapter = None
            self.verse = None
        elif name == "CHAPTER":
            num = attrs.get("cnumber") or ""
            if num.isdigit():
                self.chapter = (self.book, int(num))
            self.verse = None
            self.buf = []
        elif name == "VERS":
            if self.verse is not None:
                self._flush(self.chapter, self.verse)
            num = attrs.get("vnumber") or ""
            if num.isdigit():
                self.verse = int(num)
            self.buf = []
        elif name == "CAPTION":
            self.stats["caption"] += 1

    def close(self, name):
        if self.stack:
            self.stack.pop()
        if name == "VERS":
            self._flush(self.chapter, self.verse)
            self.verse = None
            self.buf = []
        elif name == "CHAPTER":
            self.verse = None
            self.buf = []


_OSIS_ID_TO_USFM = {
    "Gen": "GEN", "Exod": "EXO", "Lev": "LEV", "Num": "NUM", "Deut": "DEU",
    "Josh": "JOS", "Judg": "JDG", "Ruth": "RUT", "1Sam": "1SA", "2Sam": "2SA",
    "1Kgs": "1KI", "2Kgs": "2KI", "1Chr": "1CH", "2Chr": "2CH", "Ezra": "EZR",
    "Neh": "NEH", "Esth": "EST", "Job": "JOB", "Ps": "PSA", "Psalms": "PSA",
    "Prov": "PRO", "Eccl": "ECC", "Song": "SNG", "Isa": "ISA", "Jer": "JER",
    "Lam": "LAM", "Ezek": "EZK", "Dan": "DAN", "Hos": "HOS", "Joel": "JOL",
    "Amos": "AMO", "Obad": "OBA", "Jonah": "JON", "Mic": "MIC", "Nah": "NAM",
    "Hab": "HAB", "Zeph": "ZEP", "Hag": "HAG", "Zech": "ZEC", "Mal": "MAL",
    "Matt": "MAT", "Mark": "MRK", "Luke": "LUK", "John": "JHN", "Acts": "ACT",
    "Rom": "ROM", "1Cor": "1CO", "2Cor": "2CO", "Gal": "GAL", "Eph": "EPH",
    "Phil": "PHP", "Col": "COL", "1Thess": "1TH", "2Thess": "2TH",
    "1Tim": "1TI", "2Tim": "2TI", "Titus": "TIT", "Phlm": "PHM",
    "Heb": "HEB", "Jas": "JAS", "1Pet": "1PE", "2Pet": "2PE", "1John": "1JN",
    "2John": "2JN", "3John": "3JN", "Jude": "JUD", "Rev": "REV",
}

_ROMAN = {"i": "1", "ii": "2", "iii": "3", "1": "1", "2": "2", "3": "3"}


def _name_keys(name):
    """Normalised lookup keys for a book display name.

    Independent of the converter: 'I Samuel', '1st Samuel', 'The First Book of
    Samuel' and '1Samuel' all have to reach '1samuel'.  Punctuation and case go
    first, then the Roman/ordinal prefixes, then the display-name synonyms the
    scrollmapper dumps use -- all with whitespace collapsed to single spaces.
    """
    n = re.sub(r"[^a-z0-9 ]+", " ", norm_text(name).lower())
    n = re.sub(r"\s+", " ", n).strip()
    keys = {n}
    for src, dst in (("revelation of john", "revelation"),
                     ("apocalypse", "revelation"),
                     ("song of songs", "song of solomon"), ("psalms", "psalm"),
                     ("the acts of the apostles", "acts"),
                     ("the first book of", ""), ("the second book of", ""),
                     ("the third book of", ""), ("the book of", ""),
                     ("the preacher", ""), ("the epistle", ""),
                     ("the gospel according to", "")):
        if src in n:
            n2 = n.replace(src, dst)
            n2 = re.sub(r"\s+", " ", n2).strip()
            if n2:
                keys.add(n2)
    n3 = re.sub(r"^i{1,3}\b", lambda m: _ROMAN[m.group(0)] + " ", n)
    n3 = re.sub(r"^(1|2|3)(st|nd|rd|th)\b", r"\1 ", n3)
    n3 = re.sub(r"\s+", " ", n3).strip()
    keys.add(n3)
    return {k for k in keys if k}


def build_name_index(canon):
    """{name key -> USFM id} built from the canonical books.json plus ids/shorts."""
    idx = {}
    for i, b in enumerate(canon or []):
        usfm = USFM_ORDER[i]
        idx[usfm.lower()] = usfm
        for key in _name_keys(b.get("name") or ""):
            idx[key] = usfm
        short = (b.get("short") or "").lower()
        if short:
            idx[short] = usfm
            idx[re.sub(r"^(1|2|3)", r"\1", short)] = usfm
    return idx


class SjsonReader:
    """scrollmapper-style {"books":[{name, chapters:[{verses:[{text}]}]}]} dump.

    The verse text is a STRING carrying inline OSIS markup, so it is scanned
    with a small tag state machine: apparatus elements are dropped together
    with their content, everything else contributes its text.
    """

    def __init__(self, drop_tags, keep_tags=("add",)):
        self.drop_tags = {t.lower() for t in drop_tags}
        self.keep_tags = {t.lower() for t in keep_tags}

    def strip_markup(self, text):
        out = []
        depth = 0
        for m in re.finditer(r"<(/?)([A-Za-z][\w:.-]*)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)(/?)>|([^<]+)",
                             text):
            if m.group(5) is not None:
                if not depth:
                    out.append(m.group(5))
                continue
            closing, name, _attrs, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
            if closing:
                if depth:
                    depth -= 1
                continue
            low = name.lower()
            if depth:
                if not selfclose:
                    depth += 1
                continue
            if low in self.drop_tags and low not in self.keep_tags:
                if not selfclose:
                    depth = 1
                continue
        return "".join(out)

    @staticmethod
    def unescape(text):
        def repl(m):
            e = m.group(0)[1:-1]
            try:
                if e[:2] in ("#x", "#X"):
                    return chr(int(e[2:], 16))
                if e.startswith("#"):
                    return chr(int(e[1:]))
            except ValueError:
                return " "
            return {"amp": "&", "lt": "<", "gt": ">", "quot": '"',
                    "apos": "'", "nbsp": " "}.get(e, " ")
        return ENTITY_RE.sub(repl, text)


def detect_format(path, override=None):
    """Dialect sniffing from the first bytes (independent of convert_bible.py)."""
    if override and override != "auto":
        return override
    with open(path, "rb") as fh:
        head = fh.read(4096)
    txt = head.decode("utf-8", "replace").lower()
    if "<xmlbible" in txt or "<biblebook" in txt:
        return "zefania"
    if "<osistext" in txt or "<osis" in txt or 'type="book"' in txt:
        return "osis"
    if '"books"' in txt or head.lstrip()[:1] == b"{":
        return "sjson"
    if "<usfx" in txt or "<bible" in txt:
        return "usfx"
    raise SystemExit(f"verify_translation: cannot detect Bible format of {path}; "
                     f"pass --format")


FORMAT_GLOBS = {"usfx": ("*.usfx.xml", "*.usfx"),
                "osis": ("*.osis.xml", "*.osis"),
                "zefania": ("*.zefania.xml", "*.zefania"),
                "sjson": ("*.json",),
                "eBible": ("*.ebible", "*.xml", "*.txt")}


def resolve_source(bld, raw_root=None, explicit=None, note=None):
    """-> (path, how) for the raw whole-Bible file a build was made from.

    Order: --source, then the `source` recorded in build-report.json, then the
    standard raw layout `<bible-sources>/raw/<lang>-<...>`.  Returns (None, why)
    only when every candidate is missing, which check_roundtrip turns into a
    hard failure -- the ground-truth comparison may never be skipped.
    """
    if explicit:
        if os.path.isfile(explicit):
            return explicit, "--source"
        return None, f"--source {explicit} does not exist"
    claimed = bld.report.get("source") if isinstance(bld.report, dict) else None
    if claimed:
        if os.path.isfile(claimed):
            return claimed, "build-report.json"
        if note is not None:
            note.append(f"build-report.json records a source that is not on this "
                        f"machine: {claimed}")
        else:
            return None, f"build-report.json source is missing: {claimed}"
    parents = []
    if raw_root:
        parents.append(raw_root)
    pp = os.path.dirname(os.path.dirname(bld.path))
    parents.append(os.path.join(pp, "raw"))
    fmt = (bld.report or {}).get("format") or ""
    pats = FORMAT_GLOBS.get(fmt, ())
    pats = pats + tuple(g for f, g in FORMAT_GLOBS.values() for g in f)
    seen = []
    for root in parents:
        if not os.path.isdir(root):
            continue
        for lang in bld.lang_keys():
            for pat in pats:
                seen.extend(sorted(glob.glob(os.path.join(root, pat.replace("*", lang + "-*")))))
                seen.extend(sorted(glob.glob(os.path.join(root, pat.replace("*", lang + "*")))))
        if seen:
            break
    uniq = [h for i, h in enumerate(seen) if h not in seen[:i]]
    for pat in pats:                      # format-correct candidates first
        for h in uniq:
            if fnmatch.fnmatch(h, os.path.join(os.path.dirname(h), pat.replace("*", os.path.basename(h).split("-")[0] + "*"))):
                return h, f"raw layout ({fmt or 'any'})"
    if uniq:
        return uniq[0], "raw layout (format unconfirmed)"
    return None, "no source recorded in build-report.json and none found in the raw layout"


def parse_source(path, fmt, canon=None, index=None):
    """-> (books {usfm: {ch: [(v, text)]}}, names, stats)."""
    if fmt in ("usfx", "eBible"):
        r = UsfxReader()
    elif fmt == "osis":
        r = OsisReader()
    elif fmt in ("zefania", "zefania-xml"):
        r = ZefaniaReader()
    else:
        data = json.load(open(path, encoding="utf-8"))
        idx = index or build_name_index(canon)
        reader = SjsonReader(DROP_CONTENT | {"hi", "q", "foreign", "variant",
                                             "transChange", "listItem", "seg"})
        books = collections.defaultdict(dict)
        names = {}
        stats = collections.Counter()
        unmatched = []
        for b in data.get("books", []):
            nm = b.get("name") or ""
            usfm = None
            for key in sorted(_name_keys(nm), key=len, reverse=True):
                if key in idx:
                    usfm = idx[key]
                    break
            if usfm is None:
                unmatched.append(nm)
                continue
            if nm:
                names.setdefault(usfm, norm_text(nm))
            for c in b.get("chapters") or []:
                try:
                    cn = int(c.get("chapter"))
                except (TypeError, ValueError):
                    continue
                rows = []
                for v in c.get("verses") or []:
                    try:
                        vn = int(v.get("verse"))
                    except (TypeError, ValueError):
                        continue
                    raw = v.get("text") or ""
                    stats["transchange"] += raw.count("<transChange")
                    rows.append((vn, norm_text(reader.unescape(reader.strip_markup(raw)))))
                if rows:
                    books[usfm][cn] = sorted(rows)
        if unmatched:
            stats["unmatched_book_names"] = len(set(unmatched))
        return dict(books), names, stats
    r.parse(path)
    return r.sorted_books(), r.names, r.stats


# --------------------------------------------------------------------------
# build loading
# --------------------------------------------------------------------------
class Build:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.lang = os.path.basename(self.path.rstrip("/"))
        self.errors = []
        self.content = {}          # n -> {ch: [(v, text)]}
        self.meta = []             # books.json rows
        self.report = None
        self.disclosure = None
        self._load()

    def _load(self):
        mpath = os.path.join(self.path, "books.json")
        if os.path.isfile(mpath):
            try:
                self.meta = json.load(open(mpath, encoding="utf-8"))
            except Exception as exc:
                self.errors.append(f"books.json unreadable: {exc}")
        else:
            self.errors.append("books.json missing")
        for n in range(1, 67):
            p = os.path.join(self.path, f"{n}.json")
            if not os.path.isfile(p):
                self.errors.append(f"{n}.json missing")
                continue
            try:
                raw = json.load(open(p, encoding="utf-8"))
            except Exception as exc:
                self.errors.append(f"{n}.json unreadable: {exc}")
                continue
            chapters = {}
            for ch, rows in (raw or {}).items():
                try:
                    cn = int(ch)
                except (TypeError, ValueError):
                    self.errors.append(f"book {n}: non-numeric chapter key {ch!r}")
                    continue
                out = []
                for row in rows or []:
                    if not isinstance(row, dict) or "v" not in row:
                        self.errors.append(f"book {n} ch {cn}: malformed verse row")
                        continue
                    try:
                        vn = int(row["v"])
                    except (TypeError, ValueError):
                        self.errors.append(f"book {n} ch {cn}: non-numeric verse {row.get('v')!r}")
                        continue
                    out.append((vn, row.get("text") or ""))
                chapters[cn] = out
            self.content[n] = chapters
        rpath = os.path.join(self.path, "build-report.json")
        if os.path.isfile(rpath):
            try:
                self.report = json.load(open(rpath, encoding="utf-8"))
            except Exception as exc:
                self.errors.append(f"build-report.json unreadable: {exc}")
        dpath = os.path.join(self.path, "DISCLOSURE.json")
        self.disclosure_path = dpath
        if os.path.isfile(dpath):
            try:
                self.disclosure = json.load(open(dpath, encoding="utf-8"))
            except Exception as exc:
                self.errors.append(f"DISCLOSURE.json unreadable: {exc}")

    def lang_keys(self):
        """Candidate language codes: the one the converter recorded, then the
        directory name (dirs such as `polug`/`ita-clean` are cosmetic twins)."""
        keys = []
        if isinstance(self.report, dict) and isinstance(self.report.get("lang"), str):
            keys.append(self.report["lang"])
        keys.append(self.lang)
        out = []
        for k in keys:
            if k and k not in out:
                out.append(k)
        return out

    def lang_match(self, table):
        for k in self.lang_keys():
            if k in table:
                return k
        return None

    # -- iteration -------------------------------------------------------
    def iter_verses(self):
        """(n, usfm, ch, v, text) for every verse, in file order."""
        for n in sorted(self.content):
            usfm = USFM_ORDER[n - 1] if 1 <= n <= 66 else "?"
            for ch in sorted(self.content[n]):
                for v, text in self.content[n][ch]:
                    yield n, usfm, ch, v, text

    def totals(self):
        chapters = sum(len(c) for c in self.content.values())
        verses = sum(len(r) for c in self.content.values() for r in c.values())
        return {"books": len(self.content), "chapters": chapters, "verses": verses}

    def ref(self, usfm, ch, v):
        return f"{usfm}.{ch}:{v}"


# --------------------------------------------------------------------------
# findings
# --------------------------------------------------------------------------
class Result:
    def __init__(self, build):
        self.build = build
        self.findings = []
        self.checks = collections.OrderedDict()
        self.stats = {}

    def add(self, cid, severity, title, count=None, refs=None, detail=None):
        f = {"check": cid, "severity": severity, "title": title}
        if count is not None:
            f["count"] = count
        if detail:
            f["detail"] = detail
        if refs:
            f["refs"] = refs[:200]
        self.findings.append(f)
        prev = self.checks.get(cid)
        rank = {"info": 0, "warn": 1, "fail": 2}
        if prev is None or rank[severity] > rank[prev["severity"]]:
            self.checks[cid] = {"severity": severity, "title": title,
                                "count": count if count is not None else 1}
        return f

    def severities(self):
        out = set()
        for f in self.findings:
            out.add(f["severity"])
        return out

    def exit_code(self):
        sev = self.severities()
        if "fail" in sev:
            return 1
        if "warn" in sev:
            return 2
        return 0

    def verdict(self):
        return {0: "PASS", 1: "FAIL", 2: "WARN"}[self.exit_code()]

    def as_dict(self):
        return {
            "build": self.build.path,
            "lang": self.build.lang,
            "exit": self.exit_code(),
            "verdict": self.verdict(),
            "totals": self.build.totals(),
            "stats": self.stats,
            "checks": self.checks,
            "findings": self.findings,
        }


def load_canon(path):
    """Canonical books.json -- a file, or a directory containing one."""
    if not path:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, "cet", "EXALTED", "data", "books.json")
    if os.path.isdir(path):
        path = os.path.join(path, "books.json")
    if not os.path.isfile(path):
        return None, path
    try:
        rows = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None, path
    if isinstance(rows, dict):
        rows = rows.get("books", [])
    return rows, path


# --------------------------------------------------------------------------
# CHECK 1 -- doubled text
# --------------------------------------------------------------------------
def check_doubled(bld, res, src=None, top=8):
    """Detect whole-string repeats (the known converter doubling bug).

    Reported as candidates with a ratio, never as "all bugs": a verse may
    legitimately repeat itself. When a source parse is available every
    candidate is classified -- a candidate whose source text equals its own
    first half is a converter artefact; one whose source text equals the whole
    built string is a repeat that exists in the edition itself.
    """
    per_book = collections.Counter()
    refs = []
    classified = collections.Counter()
    kinds = collections.Counter()
    total = 0
    for _n, usfm, ch, v, text in bld.iter_verses():
        total += 1
        if not text:
            continue
        if exact_double_split(text) is not None:
            kind = "exact"
        elif is_doubled_ish(text):
            kind = "half"
        elif repeat_prefix_split(text):
            kind = "prefix40"
        else:
            continue
        kinds[kind] += 1
        per_book[usfm] += 1
        if len(refs) < top * 4:
            refs.append(bld.ref(usfm, ch, v))
        if src:
            srows = dict(src.get(usfm, {}).get(ch, []))
            if v in srows:
                kind_pair = classify_pair(text, srows[v])
                if kind_pair in ("doubled", "prefix_repeat"):
                    classified["converter_double"] += 1
                elif kind_pair == "exact":
                    classified["edition_repeat"] += 1
                else:
                    classified["unknown"] += 1
            else:
                classified["no_source_verse"] += 1
    ratio = (sum(per_book.values()) / total) if total else 0.0
    res.stats["doubled"] = {
        "candidates": sum(per_book.values()),
        "ratio": round(ratio, 5),
        "verses": total,
        "kinds": dict(kinds),
        "classified": dict(classified),
        "per_book": dict(per_book.most_common()),
    }
    if not per_book:
        res.add("doubled_text", "info", "no doubled-text candidates",
                count=0)
        return
    if src:
        conv = classified.get("converter_double", 0)
        edit = classified.get("edition_repeat", 0)
        unk = classified.get("unknown", 0)
        nosrc = classified.get("no_source_verse", 0)
        # A candidate the source edition itself contains is NOT a defect: the
        # repetition is authored, so only a ratio worth reporting remains.
        sev = "warn" if (conv == 0 and unk == 0 and nosrc == 0) else "fail"
        res.add("doubled_text", sev,
                f"{sum(per_book.values())} doubled-text candidates "
                f"({ratio*100:.1f}% of verses): {conv} confirmed converter "
                f"duplication, {edit} present in the source edition, "
                f"{unk} unexplained, {nosrc} with no source verse",
                count=sum(per_book.values()), refs=refs,
                detail="per-book: " + ", ".join(f"{k}:{c}" for k, c in
                                                per_book.most_common(8)))
    else:
        res.add("doubled_text", "warn",
                f"{sum(per_book.values())} doubled-text candidates "
                f"({ratio*100:.1f}%) - no source, UNCLASSIFIED",
                count=sum(per_book.values()), refs=refs)


# --------------------------------------------------------------------------
# CHECK 2 -- round trip against the raw source
# --------------------------------------------------------------------------
def classify_pair(built, source):
    """exact | ws | punct | doubled | prefix_repeat | text"""
    b, s = norm_text(built), norm_text(source)
    if b == s:
        return "exact"
    if not b and not s:
        return "exact"
    # An empty source verse that the build fills with a placeholder is a FILL,
    # not a wording change; check_gaps decides whether it was disclosed.
    if not s and b and _is_gap(b):
        return "filled"
    # The reverse -- source text, nothing in the build -- is an erasure.
    if b and not s:
        return "erased"
    if b == s + s:
        return "doubled"
    # ditto: the seam separator makes "src src" != "srcsrc" for short verses,
    # which is how a duplicated Korean parenthetical ended up filed as a
    # WORDING delta instead of the duplication it is.
    bs, ss = re.sub(r"\s+", "", b), re.sub(r"\s+", "", s)
    if bs and bs == ss + ss:
        return "doubled"
    # Inline <note>/<hi> inside a verse: the converter emits the text before
    # the markup and then the whole verse, so the built string is the source
    # verse with its OWN opening run inserted a second time.
    if ss and len(bs) > len(ss) and bs.endswith(ss) and \
            ss.startswith(bs[:len(bs) - len(ss)]):
        return "prefix_repeat"
    if is_doubled_ish(b) and loose_key(s) in (loose_key(b[:len(b) // 2]),
                                              loose_key(b)):
        return "doubled"
    if re.sub(r"\s+", "", b) == re.sub(r"\s+", "", s):
        return "ws"
    if loose_key(b) == loose_key(s):
        return "punct"
    return "text"


def check_roundtrip(bld, res, src, src_path, top=8, fmt=None):
    """Ground truth: every verse of the source must equal the built verse."""
    if not src:
        res.add("roundtrip", "fail",
                "no raw source available - the ground-truth check cannot be "
                "skipped; pass --source", count=0)
        res.stats["roundtrip"] = {}
        return
    counts = collections.Counter()
    samples = collections.defaultdict(list)
    src_verses = 0
    for usfm in USFM_ORDER:
        sch = src.get(usfm)
        if not sch:
            continue
        n = USFM_INDEX[usfm] + 1
        bch = bld.content.get(n, {})
        for ch in sorted(sch):
            srows = dict(sch[ch])
            brows = dict(bch.get(ch, []))
            for v in sorted(srows):
                src_verses += 1
                if v not in brows:
                    counts["absent"] += 1
                    if len(samples["absent"]) < top * 3:
                        samples["absent"].append(bld.ref(usfm, ch, v))
                    continue
                kind = classify_pair(brows[v], srows[v])
                counts[kind] += 1
                if kind != "exact" and len(samples[kind]) < top * 3:
                    samples[kind].append(
                        f"{bld.ref(usfm, ch, v)} built={brows[v][:70]!r} "
                        f"src={srows[v][:70]!r}")
            for v in sorted(set(brows) - set(srows)):
                counts["extra"] += 1
                if len(samples["extra"]) < top * 3:
                    samples["extra"].append(f"{bld.ref(usfm, ch, v)} "
                                            f"built={brows[v][:70]!r}")
    if src_verses == 0:
        got = sorted(src)[:8]
        res.add("roundtrip", "fail",
                f"the independent parse of {src_path} yielded 0 verses in the "
                f"canonical 66 (book ids seen: {got}) - the ground-truth "
                f"comparison is IMPOSSIBLE, not skipped", count=0)
        res.stats["roundtrip"] = {"source": src_path, "format": fmt,
                                  "source_verses": 0, "exact": 0, "mismatch": 0,
                                  "classes": {}}
        return
    extra_books = sorted(b for b in src if b not in USFM_INDEX)
    if extra_books:
        res.add("roundtrip", "warn",
                f"{len(extra_books)} source book(s) are outside the canonical "
                f"66 and were not compared: {extra_books[:8]}",
                count=len(extra_books))
    exact = counts["exact"]
    mismatch = src_verses - exact
    res.stats["roundtrip"] = {
        "source": src_path,
        "format": fmt,
        "source_verses": src_verses,
        "exact": exact,
        "mismatch": mismatch,
        "classes": {k: counts[k] for k in
                    ("ws", "punct", "doubled", "prefix_repeat", "text",
                     "filled", "erased", "absent", "extra")},
        "accuracy": round(exact / src_verses, 5) if src_verses else 0.0,
    }
    for kind in ("absent", "extra", "text", "erased", "doubled",
                 "prefix_repeat", "filled", "ws", "punct"):
        c = counts[kind]
        if not c:
            continue
        if kind in ("ws", "punct"):
            res.add("roundtrip", "warn",
                    f"{c} verse(s) differ from the source only in "
                    f"{'spacing' if kind == 'ws' else 'punctuation/case'}",
                    count=c, refs=samples[kind])
        elif kind == "doubled":
            res.add("roundtrip", "fail",
                    f"{c} verse(s) in the build are the source verse repeated "
                    f"end to end (converter duplication)", count=c,
                    refs=samples[kind])
        elif kind == "erased":
            res.add("roundtrip", "fail",
                    f"{c} verse(s) are EMPTY in the build but carry text in "
                    f"the source", count=c, refs=samples[kind])
        elif kind == "filled":
            res.add("roundtrip", "warn",
                    f"{c} verse(s) are empty in the source and carry a "
                    f"placeholder in the build (see the gaps/DISCLOSURE "
                    f"check for whether it is declared)", count=c,
                    refs=samples[kind])
        elif kind == "prefix_repeat":
            res.add("roundtrip", "fail",
                    f"{c} verse(s) repeat their own opening run before the full "
                    f"verse (inline markup emitted twice)", count=c,
                    refs=samples[kind])
        elif kind == "absent":
            res.add("missing_verses", "fail",
                    f"{c} verse(s) exist in the source but are ABSENT from the "
                    f"build", count=c, refs=samples[kind])
        elif kind == "extra":
            res.add("roundtrip", "fail",
                    f"{c} verse(s) in the build are absent from the source",
                    count=c, refs=samples[kind])
        else:
            res.add("roundtrip", "fail",
                    f"{c} verse(s) differ in WORDING from the source",
                    count=c, refs=samples[kind])
    # per-book absent summary, the shape a converter fix needs
    absent_by_book = collections.Counter()
    for usfm in USFM_ORDER:
        n = USFM_INDEX[usfm] + 1
        bch = bld.content.get(n, {})
        for ch, rows in (src.get(usfm) or {}).items():
            have = {v for v, _ in bch.get(ch, [])}
            absent_by_book[usfm] += sum(1 for v, _ in rows if v not in have)
    if absent_by_book:
        res.stats["roundtrip"]["absent_per_book"] = dict(
            absent_by_book.most_common())
    if not mismatch and not counts["extra"]:
        res.add("roundtrip", "info",
                f"all {exact} source verses reproduced exactly", count=exact)


# --------------------------------------------------------------------------
# CHECK 3 -- forbidden tokens / surviving markup
# --------------------------------------------------------------------------
def check_forbidden(bld, res, top=8):
    hits = collections.defaultdict(list)
    ent_hits = []
    tag_hits = []
    for _n, usfm, ch, v, text in bld.iter_verses():
        for ch_ in text:
            if ch_ in FORBIDDEN_CHARS or CONTROL_RE.match(ch_):
                hits[usfm].append(bld.ref(usfm, ch, v))
                break
        m = ENTITY_RE.search(text)
        if m:
            ent_hits.append(f"{bld.ref(usfm, ch, v)} {m.group(0)}")
        if ANGLE_TAG_RE.search(text):
            tag_hits.append(f"{bld.ref(usfm, ch, v)} "
                            f"{ANGLE_TAG_RE.search(text).group(0)[:40]!r}")
    total = sum(len(x) for x in hits.values())
    if total:
        refs = [r for lst in hits.values() for r in lst][:top * 3]
        res.add("forbidden_tokens", "fail",
                f"{total} verse(s) carry a redscript-hostile character "
                f"({', '.join(repr(c) for c in FORBIDDEN_CHARS)} or a control char)",
                count=total, refs=refs)
    else:
        res.add("forbidden_tokens", "info",
                "no { } ~ pilcrow backslash or control characters in verse text",
                count=0)
    if ent_hits:
        res.add("markup_residue", "fail",
                f"{len(ent_hits)} verse(s) ship raw XML entity text "
                f"(e.g. &quot;) -- the entity was never decoded",
                count=len(ent_hits), refs=ent_hits[:top * 3])
    if tag_hits:
        res.add("markup_residue", "fail",
                f"{len(tag_hits)} verse(s) ship raw angle-bracket markup",
                count=len(tag_hits), refs=tag_hits[:top * 3])
    res.stats["forbidden"] = {"chars": total, "entities": len(ent_hits),
                              "tags": len(tag_hits)}


# --------------------------------------------------------------------------
# CHECK 4 -- structure
# --------------------------------------------------------------------------
def check_structure(bld, res, canon=None, top=8, src=None):
    problems = []
    # A verse number the EDITION itself lacks (e.g. Finnish MAT 17:21) is
    # faithful, not a defect: those are collected separately and only warned
    # about, and only when the source agrees.
    edition_gaps = []
    if bld.errors:
        problems.extend(bld.errors[:top * 2])
    if len(bld.content) != 66:
        problems.append(f"{len(bld.content)} book files present, expected 66")
    n_meta = len(bld.meta)
    if n_meta != 66:
        problems.append(f"books.json has {n_meta} rows, expected 66")
    for i, row in enumerate(bld.meta[:66], start=1):
        if row.get("n") != i:
            problems.append(f"books.json row {i} has n={row.get('n')!r}")
        usfm = USFM_ORDER[i - 1]
        chapters = bld.content.get(i, {})
        cnums = sorted(chapters)
        if cnums != list(range(1, len(cnums) + 1)):
            missing = sorted(set(range(1, (max(cnums) if cnums else 0) + 1)) - set(cnums))
            dups = [c for c, k in collections.Counter(cnums).items() if k > 1]
            src_ch = set(src.get(usfm, {})) if src else None
            novel = [c for c in missing
                     if src_ch is None or c in src_ch]
            same = [c for c in missing if c not in novel]
            if dups:
                problems.append(f"{usfm}: duplicate chapter numbers {dups[:6]}")
            if novel:
                problems.append(
                    f"{usfm}: chapters not contiguous 1..{len(cnums)} "
                    f"(missing={novel[:6]})")
            for c in same:
                edition_gaps.append(f"{usfm} chapter {c}")
        verses_here = 0
        for ch in cnums:
            nums = [v for v, _ in chapters[ch]]
            uniq = sorted(set(nums))
            dups = [v for v, k in collections.Counter(nums).items() if k > 1]
            gaps = sorted(set(range(1, (max(uniq) if uniq else 0) + 1)) - set(uniq))
            if dups or gaps or uniq != list(range(1, len(uniq) + 1)):
                msgs = []
                if dups:
                    msgs.append(f"dups={dups[:6]}")
                    problems.append(f"{usfm} {ch}: duplicate verse numbers "
                                    f"{dups[:6]}")
                novel = []
                for g in gaps:
                    src_nums = {v for v, _ in src.get(usfm, {}).get(ch, [])} if src else None
                    # the build lost a verse the SOURCE carries -> a real drop;
                    # the source lacks it too -> the edition itself has no v{g}.
                    if src_nums is None or g in src_nums:
                        novel.append(g)
                    else:
                        edition_gaps.append(f"{usfm} {ch}:{g}")
                if novel:
                    msgs.append(f"gaps={novel[:6]}")
                    problems.append(f"{usfm} {ch}: verse numbers not "
                                    f"1..{len(uniq)} (n={len(nums)} "
                                    f"gaps={novel[:6]})")
                elif gaps:
                    msgs.append(f"edition gaps={gaps[:6]}")
            verses_here += len(nums)
        if row.get("chapters") != len(cnums):
            problems.append(f"{usfm}: books.json chapters={row.get('chapters')!r} "
                            f"but the JSON has {len(cnums)}")
        if row.get("verses") != verses_here:
            problems.append(f"{usfm}: books.json verses={row.get('verses')!r} "
                            f"but the JSON has {verses_here}")
        if "id" in row and row["id"] != usfm:
            problems.append(f"{usfm}: books.json id={row['id']!r}")
    if edition_gaps:
        res.add("edition_versification", "warn",
                f"{len(edition_gaps)} verse number(s) are absent in the SOURCE "
                f"edition too - faithful to the tradition, not a build defect",
                count=len(edition_gaps), refs=edition_gaps[:top * 4])
    if problems:
        res.add("structure", "fail",
                f"{len(problems)} structural problem(s)", count=len(problems),
                refs=problems[:top * 4])
    else:
        res.add("structure", "info",
                "66 books, canonical order, contiguous chapters/verses, "
                "books.json agrees with the JSON", count=0)

    # versification deltas vs the canonical KJV: legitimate in many traditions
    deltas = []
    if canon and len(canon) >= 66:
        for i, _row in enumerate(bld.meta[:66], start=1):
            usfm = USFM_ORDER[i - 1]
            try:
                cc, cv = int(canon[i - 1]["chapters"]), int(canon[i - 1]["verses"])
            except (KeyError, TypeError, ValueError):
                continue
            gc = len(bld.content.get(i, {}))
            gv = sum(len(r) for r in bld.content.get(i, {}).values())
            if gc != cc or gv != cv:
                deltas.append(f"{usfm}: {gc}ch/{gv}v vs KJV {cc}ch/{cv}v")
        if deltas:
            res.add("versification", "warn",
                    f"{len(deltas)} book(s) differ from the canonical KJV "
                    f"chapter/verse counts (may be a legitimate tradition)",
                    count=len(deltas), refs=deltas[:top * 4],
                    detail=f"chapters={bld.totals()['chapters']} "
                           f"verses={bld.totals()['verses']} "
                           f"(KJV 1189/31102)")
        else:
            res.add("versification", "info",
                    "chapter and verse counts match the canonical KJV", count=0)
    res.stats["structure"] = {"problems": len(problems), "deltas": len(deltas),
                              "edition_gaps": len(edition_gaps)}


# --------------------------------------------------------------------------
# CHECK 5 -- `short` slug safety (NETdir:// URL segments)
# --------------------------------------------------------------------------
_UNSAFE_SLUG = re.compile(r"[^A-Za-z0-9._~-]")


def check_slugs(bld, res, canon=None, top=8):
    bad = []
    seen = {}
    for i, row in enumerate(bld.meta, start=1):
        short = row.get("short")
        ref = f"books.json row {i} ({USFM_ORDER[i-1] if i <= 66 else '?'})"
        if not short:
            bad.append(f"{ref}: short is empty")
            continue
        if not isinstance(short, str):
            bad.append(f"{ref}: short is {type(short).__name__}, expected string")
            continue
        if not short.isascii():
            bad.append(f"{ref}: short={short!r} is not ASCII "
                       f"(breaks NETdir:// URL segments)")
            continue
        m = _UNSAFE_SLUG.search(short)
        if m:
            bad.append(f"{ref}: short={short!r} contains unsafe {m.group(0)!r} "
                       f"(no space, slash, backslash or colon allowed)")
        if short in seen:
            bad.append(f"{ref}: short={short!r} duplicates row {seen[short]}")
        else:
            seen[short] = i
    drift = []
    if canon and len(canon) >= 66:
        for i, row in enumerate(bld.meta[:66], start=1):
            cs = (canon[i - 1] or {}).get("short")
            if cs and row.get("short") != cs:
                drift.append(f"{USFM_ORDER[i-1]}: short={row.get('short')!r} but "
                             f"canonical KJV uses {cs!r}")
    if bad:
        res.add("short_slug", "fail", f"{len(bad)} unusable `short` slug(s)",
                count=len(bad), refs=bad[:top * 4])
    else:
        res.add("short_slug", "info",
                f"all {len(bld.meta)} `short` slugs are ASCII, unique and "
                f"URL-segment safe", count=len(bld.meta))
    if drift:
        res.add("short_slug", "warn",
                f"{len(drift)} `short` slug(s) drifted from the canonical KJV "
                f"(in-game URLs would change)", count=len(drift),
                refs=drift[:top * 4])
    res.stats["slugs"] = {"bad": len(bad), "drift": len(drift)}


# --------------------------------------------------------------------------
# CHECK 6 -- empty text, gap markers, DISCLOSURE reconciliation
# --------------------------------------------------------------------------
def _is_gap(text):
    if not text or not text.strip():
        return "empty"
    for pat in GAP_PATTERNS:
        if pat.search(text):
            return "marker"
    return None


def check_gaps(bld, res, top=8):
    empties = []
    markers = []
    for _n, usfm, ch, v, text in bld.iter_verses():
        kind = _is_gap(text)
        if kind == "empty":
            empties.append(bld.ref(usfm, ch, v))
        elif kind == "marker":
            markers.append(bld.ref(usfm, ch, v))
    disclosed = set()
    entries = []
    if bld.disclosure:
        for e in bld.disclosure.get("entries") or []:
            entries.append(e)
            if e.get("book") and e.get("chapter") is not None and e.get("verse") is not None:
                disclosed.add((e["book"], int(e["chapter"]), int(e["verse"])))
    undisclosed = []
    for _n, usfm, ch, v, text in bld.iter_verses():
        if _is_gap(text) and (usfm, ch, v) not in disclosed:
            undisclosed.append(bld.ref(usfm, ch, v))
    stale = []
    gapset = {(usfm, ch, v) for n, usfm, ch, v, t in bld.iter_verses()
              if _is_gap(t)}
    for key in sorted(disclosed - gapset):
        stale.append(f"{key[0]}.{key[1]}:{key[2]}")
    if bld.disclosure is None:
        res.add("gaps", "warn",
                "DISCLOSURE.json missing - no audit record of gaps/fills for "
                "this build", count=0)
    disclosed_gaps = [r for r in (empties + markers) if r not in undisclosed]
    if undisclosed:
        res.add("undisclosed_gap", "fail",
                f"{len(undisclosed)} gap(s) (empty verse or gap marker) are NOT "
                f"disclosed in DISCLOSURE.json", count=len(undisclosed),
                refs=undisclosed[:top * 3])
    if disclosed_gaps:
        res.add("gaps", "warn",
                f"{len(disclosed_gaps)} disclosed gap(s): {len(empties)} empty "
                f"verse(s), {len(markers)} marker(s)", count=len(disclosed_gaps),
                refs=disclosed_gaps[:top * 3])
    if not empties and not markers:
        res.add("gaps", "info", "no empty verses and no gap markers", count=0)
    if stale:
        res.add("gaps", "warn",
                f"{len(stale)} DISCLOSURE entr(ies) no longer correspond to a "
                f"gap in the build", count=len(stale), refs=stale[:top * 3])
    res.stats["gaps"] = {"empty": len(empties), "markers": len(markers),
                         "undisclosed": len(undisclosed), "stale": len(stale),
                         "disclosure_entries": len(entries)}


# --------------------------------------------------------------------------
# CHECK 7 -- encoding sanity
# --------------------------------------------------------------------------
def check_encoding(bld, res, src=None, top=8):
    c1 = []
    fffd = []
    cjk = []
    nfd = []
    nbsp = 0
    src_c1 = 0
    if src:
        for chapters in src.values():
            for rows in chapters.values():
                for _v, t in rows:
                    src_c1 += sum(1 for c in t if "\u0080" <= c <= "\u009f")
    for _n, usfm, ch, v, text in bld.iter_verses():
        if any("\u0080" <= c <= "\u009f" for c in text):
            c1.append(bld.ref(usfm, ch, v))
        if "\ufffd" in text:
            fffd.append(bld.ref(usfm, ch, v))
        nbsp += text.count("\u00a0")
        m = re.search(r"(.)\1{2,}", text)
        if m and CJK_RE.match(m.group(1)):
            cjk.append(f"{bld.ref(usfm, ch, v)} {m.group(0)!r}")
        if unicodedata.normalize("NFC", text) != text:
            flat = unicodedata.normalize("NFD", text)
            if sum(1 for c in flat if unicodedata.combining(c)) >= 2:
                nfd.append(bld.ref(usfm, ch, v))
    if c1:
        res.add("encoding", "fail",
                f"{len(c1)} verse(s) still contain C1 mojibake "
                f"(U+0080-U+009F); the source has {src_c1}",
                count=len(c1), refs=c1[:top * 3])
    if fffd:
        res.add("encoding", "fail",
                f"{len(fffd)} verse(s) contain U+FFFD replacement characters",
                count=len(fffd), refs=fffd[:top * 3])
    if cjk:
        res.add("encoding", "warn",
                f"{len(cjk)} verse(s) contain a run of 3+ identical CJK "
                f"characters (doubled-word reduplication is legitimate in "
                f"zh/ko; check the source)", count=len(cjk),
                refs=cjk[:top * 3])
    if nfd:
        sev = "fail" if bld.lang_match(PRECOMPOSED) else "warn"
        res.add("encoding", sev,
                f"{len(nfd)} verse(s) ship DECOMPOSED text (combining-mark "
                f"piles) instead of precomposed forms", count=len(nfd),
                refs=nfd[:top * 3])
    if not (c1 or fffd or cjk or nfd):
        res.add("encoding", "info",
                "no C1 mojibake, no U+FFFD, no combining-mark piles",
                count=0)
    if src_c1 and not c1:
        res.add("encoding", "info",
                f"source carried {src_c1} C1 mojibake char(s); all repaired "
                f"in the build", count=src_c1)
    if nbsp:
        res.add("encoding", "info", f"{nbsp} non-breaking space(s) left in "
                f"verse text", count=nbsp)
    res.stats["encoding"] = {"c1": len(c1), "fffd": len(fffd), "cjk_runs": len(cjk),
                             "decomposed": len(nfd), "nbsp": nbsp,
                             "source_c1": src_c1}


# --------------------------------------------------------------------------
# CHECK 8 -- script / language fingerprint
# --------------------------------------------------------------------------
def check_script(bld, res, top=8):
    counts = collections.Counter()
    words = collections.Counter()
    nonascii = collections.Counter()
    tokens = 0
    letters = 0
    dia = 0
    for _n, _u, _c, _v, text in bld.iter_verses():
        for c in text:
            s = script_of(c)
            if s:
                counts[s] += 1
                letters += 1
                if s == "latin" and unicodedata.combining(c) == 0 and \
                        ("a" <= c <= "z" or "A" <= c <= "Z"):
                    pass
                try:
                    if "a" <= unicodedata.normalize("NFD", c) < "g":
                        dia += 1
                except TypeError:
                    pass
        for w in WORD_RE.findall(text):
            tokens += 1
            low = w.casefold()
            words[low] += 1
            if any(ord(c) > 127 for c in w):
                nonascii[low] += 1
    expected = LANG_SCRIPT.get(bld.lang_match(LANG_SCRIPT))
    dominant, dcount = (counts.most_common(1) or [("", 0)])[0]
    ratio = dcount / letters if letters else 0.0
    eng = sum(c for w, c in words.items() if w in ENGLISH_STOPWORDS)
    eng_ratio = eng / tokens if tokens else 0.0
    top_na = nonascii.most_common(8)
    dia_ratio = dia / letters if letters else 0.0
    res.stats["script"] = {
        "expected": expected,
        "dominant": dominant,
        "dominant_ratio": round(ratio, 4),
        "scripts": dict(counts.most_common(4)),
        "english_stopword_ratio": round(eng_ratio, 4),
        "diacritic_letter_ratio": round(dia_ratio, 4),
        "top_non_ascii_words": [[w, c] for w, c in top_na],
    }
    if not letters:
        res.add("script", "fail", "no letters at all in the build", count=0)
        return
    if expected and dominant != expected:
        res.add("script", "fail",
                f"expected {expected} script, dominant is {dominant} "
                f"({ratio*100:.1f}% of letters)", count=letters,
                refs=["top non-ASCII words: " +
                      ", ".join(f"{w}({c})" for w, c in top_na)])
    elif expected and ratio < 0.90:
        res.add("script", "warn",
                f"only {ratio*100:.1f}% of letters are {expected} "
                f"(mixed-script or partially translated build)", count=letters,
                refs=[", ".join(f"{w}({c})" for w, c in top_na)])
    else:
        res.add("script", "info",
                f"{dominant} script {ratio*100:.1f}% of letters, "
                f"English stopwords {eng_ratio*100:.1f}% of tokens",
                count=letters,
                refs=["top non-ASCII words: " +
                      ", ".join(f"{w}({c})" for w, c in top_na)] if top_na else None)
    if eng_ratio >= ENGLISH_UNTRANSLATED_THRESHOLD:
        res.add("script", "fail",
                f"{eng_ratio*100:.1f}% of tokens are English function words - "
                f"this build looks UNTRANSLATED or is the wrong language",
                count=tokens,
                refs=["most common words: " +
                      ", ".join(f"{w}({c})" for w, c in words.most_common(10))])
    if bld.lang_match(DIACRITIC_EXPECTED) and dia_ratio < 0.005:
        res.add("script", "warn",
                f"{dia_ratio*100:.2f}% diacritic letters in a language that "
                f"needs them - ASCII fallback suspected", count=letters)


# --------------------------------------------------------------------------
# CHECK 9 -- report reconciliation (+ provenance)
# --------------------------------------------------------------------------
def check_reports(bld, res, src_path=None, fmt=None, vetted=None, top=8):
    rep = bld.report
    if rep is None:
        res.add("report_reconciliation", "warn",
                "build-report.json missing - converter audit record absent",
                count=0)
    else:
        bad = []
        tot = bld.totals()
        if rep.get("total_chapters") != tot["chapters"]:
            bad.append(f"total_chapters report={rep.get('total_chapters')} "
                       f"actual={tot['chapters']}")
        if rep.get("total_verses") != tot["verses"]:
            bad.append(f"total_verses report={rep.get('total_verses')} "
                       f"actual={tot['verses']}")
        rbooks = rep.get("books") or []
        if len(rbooks) != 66:
            bad.append(f"report lists {len(rbooks)} books, expected 66")
        for i, rb in enumerate(rbooks[:66], start=1):
            ch_map = bld.content.get(i, {})
            if rb.get("chapters") != len(ch_map):
                bad.append(f"{USFM_ORDER[i-1]}: report chapters="
                           f"{rb.get('chapters')} actual={len(ch_map)}")
            gv = sum(len(r) for r in ch_map.values())
            if rb.get("verses") != gv:
                bad.append(f"{USFM_ORDER[i-1]}: report verses={rb.get('verses')} "
                           f"actual={gv}")
        if rep.get("lang") and rep["lang"] not in bld.lang_keys():
            res.add("report_reconciliation", "info",
                    f"build dir {bld.lang!r} records lang={rep.get('lang')!r}",
                    count=0)
        if fmt and rep.get("format") and rep["format"] != fmt:
            res.add("report_reconciliation", "warn",
                    f"report says format={rep['format']!r} but the source given "
                    f"is {fmt!r}", count=0)
        if bad:
            res.add("report_reconciliation", "fail",
                    f"{len(bad)} build-report.json total(s) disagree with the "
                    f"JSON files", count=len(bad), refs=bad[:top * 3])
        else:
            res.add("report_reconciliation", "info",
                    f"build-report.json totals agree ({tot['chapters']} chapters, "
                    f"{tot['verses']} verses)", count=0)
        # sanitize stats vs reality: a claimed C1 repair that left C1 behind
        san = rep.get("sanitize") or {}
        leftover = res.stats.get("encoding", {}).get("c1", 0)
        if san.get("c1_mojibake") and leftover:
            res.add("report_reconciliation", "fail",
                    f"report claims {san['c1_mojibake']} C1 repairs but "
                    f"{leftover} C1 char(s) survive in the build", count=leftover)
    if src_path:
        base = os.path.basename(src_path)
        claimed = os.path.basename(rep.get("source", "")) if rep else ""
        if claimed and claimed != base:
            res.add("provenance", "warn",
                    f"build was made from {claimed!r} but is being verified "
                    f"against {base!r}", count=0)
        if vetted:
            entry = vetted.get(bld.lang)
            if entry and entry != base:
                res.add("provenance", "warn",
                        f"VETTED.txt registers {bld.lang} -> {entry!r} but the "
                        f"build used {claimed or base!r}", count=0)
            elif entry:
                res.add("provenance", "info",
                        f"VETTED.txt lineage matches ({entry})", count=0)
    # book display names: English fallback while the source had a native title
    res.stats["reports"] = {"has_report": rep is not None,
                            "has_disclosure": bld.disclosure is not None}


def load_vetted(path):
    """{code: raw file} from the vetted-source registry, if present."""
    if not path or not os.path.isfile(path):
        return None
    out = {}
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            f = line.split()
            if len(f) >= 2 and f[0].islower() and len(f[0]) <= 5 and \
                    ("." in f[1]):
                out[f[0]] = f[1]
    except OSError:
        return None
    return out or None


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------
def run_verification(build_dir, source=None, fmt="auto", canon_rows=None,
                     canon_path=None, top=8, vetted=None, source_note="",
                     raw_root=None):
    bld = Build(build_dir)
    res = Result(bld)
    src = None
    src_meta = None
    notes = []
    resolved, how = resolve_source(bld, raw_root=raw_root, explicit=source,
                                   note=notes)
    for n in notes:
        res.add("source_resolution", "warn", n)
    source_note = f"{source_note}; {how}".strip("; ")
    if resolved is None:
        res.add("roundtrip", "fail",
                f"no raw source for this build ({how}) - the ground-truth "
                f"check cannot be skipped; pass --source", count=0)
    if resolved:
        source = resolved
        try:
            fmt = detect_format(source, fmt)
            src, names, stats = parse_source(source, fmt, canon_rows)
            src_meta = {"path": source, "format": fmt, "names": names,
                        "stats": dict(stats)}
        except SystemExit:
            raise
        except Exception as exc:
            res.add("roundtrip", "fail",
                    f"raw source could not be parsed independently: "
                    f"{type(exc).__name__}: {exc}", count=0)
    if src_meta and src_meta["stats"].get("unplaced_verse"):
        # Verses the parser could not attribute to a canonical book would be
        # silently EXCLUDED from the comparison below, so a build could look
        # clean against a source that was never really read.
        res.add("source_parse", "fail",
                f"the independent parse could not place "
                f"{src_meta['stats']['unplaced_verse']} source verse(s) in a "
                f"canonical book - the comparison would silently skip them",
                count=src_meta["stats"]["unplaced_verse"])
    check_doubled(bld, res, src=src, top=top)
    check_roundtrip(bld, res, src, source or "(none)", top=top, fmt=fmt)
    check_forbidden(bld, res, top=top)
    check_structure(bld, res, canon=canon_rows, top=top, src=src)
    check_slugs(bld, res, canon=canon_rows, top=top)
    check_gaps(bld, res, top=top)
    check_encoding(bld, res, src=src, top=top)
    check_script(bld, res, top=top)
    check_reports(bld, res, src_path=source, fmt=fmt, vetted=vetted, top=top)
    res.stats["source"] = src_meta
    if source_note:
        res.stats["source_note"] = source_note
    return res


def fmt_int(x):
    return "-" if x is None else str(x)


def table_line(res):
    st = res.stats
    rt = st.get("roundtrip") or {}
    d = st.get("doubled") or {}
    cls = rt.get("classes") or {}
    mism = cls.get("text", 0) + cls.get("doubled", 0) + cls.get("absent", 0) + \
        cls.get("extra", 0) + cls.get("ws", 0) + cls.get("punct", 0)
    sc = st.get("script") or {}
    struct = (st.get("structure") or {}).get("problems", 0)
    return "| {lang:9s} | {verdict:4s} | {doub:>7s} | {match:>7s} | {mism:>7s} | {struct:>6s} | {script}".format(
        lang=res.build.lang,
        verdict=res.verdict(),
        doub=f"{d.get('candidates', 0)} ({d.get('ratio', 0)*100:.1f}%)",
        match=fmt_int(rt.get("exact")),
        mism=fmt_int(mism),
        struct=fmt_int(struct),
        script=f"{sc.get('dominant', '?')} {sc.get('dominant_ratio', 0)*100:.1f}%"
               f" exp={sc.get('expected', '?')}"
               f" en={sc.get('english_stopword_ratio', 0)*100:.1f}%")


HEADER = ("| lang      | verdict | doubled | rt-exact | rt-diff | struct | script-fingerprint |\n"
          "| --------- | ------- | ------- | -------- | ------- | ------ | ------------------- |")


def print_result(res, verbose=False, top=8):
    print(f"=== {res.build.lang}  {res.build.path}")
    tot = res.build.totals()
    print(f"    books={tot['books']} chapters={tot['chapters']} "
          f"verses={tot['verses']}")
    src = res.stats.get("source")
    if src:
        print(f"    source={src['path']} format={src['format']}"
              + (f"  [{res.stats.get('source_note')}]"
                 if res.stats.get("source_note") else "")
              + (f"  source_names={len(src['names'])}"
                 if src.get("names") else ""))
    else:
        print("    source=NONE")
    print(HEADER)
    print(table_line(res))
    order = {"fail": 0, "warn": 1, "info": 2}
    finds = sorted(res.findings, key=lambda f: (order[f["severity"]], f["check"]))
    shown = finds if verbose else [f for f in finds if f["severity"] != "info"]
    if not shown:
        print("    no findings")
    for f in shown:
        mark = {"fail": "FAIL", "warn": "WARN", "info": "info"}[f["severity"]]
        print(f"    [{mark}] {f['check']}: {f['title']}")
        if f.get("detail"):
            print(f"           {f['detail']}")
        for ref in (f.get("refs") or [])[:top]:
            print(f"           - {ref}")
        extra = len(f.get("refs") or []) - top
        if extra > 0:
            print(f"           ... and {extra} more")
    print(f"    verdict={res.verdict()} exit={res.exit_code()}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("build_dir", nargs="?", help="build directory (or omit with --batch)")
    ap.add_argument("--source", default=None,
                    help="raw whole-Bible file the build was made from "
                         "(default: the path recorded in build-report.json)")
    ap.add_argument("--format", default="auto",
                    choices=["usfx", "osis", "zefania", "sjson", "auto"],
                    help="source dialect (auto-detected by default)")
    ap.add_argument("--canon", default=None,
                    help="canonical KJV books.json, or a directory containing "
                         "one (default: cet/EXALTED/data/books.json)")
    ap.add_argument("--raw-root", default=None,
                    help="raw source directory to search when build-report.json "
                         "does not name an existing source (default: "
                         "<bible-sources>/raw)")
    ap.add_argument("--vetted", default=None,
                    help="VETTED.txt registry for a provenance cross-check")
    ap.add_argument("--batch", metavar="ROOT", default=None,
                    help="verify every language directory under ROOT")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--verbose", action="store_true", help="all findings, more refs")
    ap.add_argument("--top", type=int, default=8, help="refs shown per finding")
    ap.add_argument("--selftest", action="store_true",
                    help="run the fixture battery and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    canon_rows, canon_path = load_canon(args.canon)
    if canon_rows is None and not args.json:
        print(f"verify_translation: canonical books.json not found at "
              f"{canon_path}", file=sys.stderr)
    vetted = load_vetted(args.vetted)
    top = args.top if not args.verbose else max(args.top, 25)

    targets = []
    if args.batch:
        for name in sorted(os.listdir(args.batch)):
            p = os.path.join(args.batch, name)
            if os.path.isdir(p) and os.path.isfile(os.path.join(p, "books.json")):
                targets.append(p)
    elif args.build_dir:
        targets.append(args.build_dir)
    else:
        ap.error("give a build directory or --batch ROOT")

    results = []
    for t in targets:
        res = run_verification(t, source=args.source, fmt=args.format,
                               canon_rows=canon_rows, top=top, vetted=vetted,
                               raw_root=args.raw_root)
        results.append(res)
        if not args.json:
            if len(targets) > 1:
                print(f"--- {res.build.lang}")
                print(HEADER)
                print(table_line(res))
                for f in sorted(res.findings,
                                key=lambda f: ({"fail": 0, "warn": 1,
                                                "info": 2}[f["severity"]],
                                               f["check"])):
                    if f["severity"] == "info" and not args.verbose:
                        continue
                    mark = {"fail": "FAIL", "warn": "WARN",
                            "info": "info"}[f["severity"]]
                    print(f"    [{mark}] {f['check']}: {f['title']}")
                    if f.get("detail"):
                        print(f"           {f['detail']}")
            else:
                print_result(res, verbose=args.verbose, top=top)
    if args.json:
        payload = [r.as_dict() for r in results]
        json.dump(payload if len(payload) > 1 else payload[0], sys.stdout,
                  ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    if len(results) > 1 and not args.json:
        print(HEADER)
        for res in results:
            print(table_line(res))
        print(f"{sum(1 for r in results if r.exit_code() == 1)} FAIL / "
              f"{sum(1 for r in results if r.exit_code() == 2)} WARN / "
              f"{len(results)} builds")
    return max([r.exit_code() for r in results] or [0])


# --------------------------------------------------------------------------
# selftest: every check must be proven to fire on a corrupted fixture
# --------------------------------------------------------------------------
SAMPLE = ("En el principio creó Dios los cielos y la tierra. "
          "Y la tierra era sin forma y vacía, y había tinieblas sobre la "
          "faz del abismo, y el Espíritu de Dios se movía sobre las aguas.")
GAP_MARK = "\u27e8missing in this edition\u27e9"


def _fixture(mutate=None):
    """A VALID mini build (66 books x 1 chapter x 1 verse) + its USFX source.

    chapters: {book_n: {chapter: [(verse, text)]}}   source: [(usfm, text)]
    """
    books, chapters, source = [], {}, []
    for i, usfm in enumerate(USFM_ORDER):
        books.append({"n": i + 1, "name": "Libro", "short": f"Bk{i + 1:02d}",
                      "chapters": 1, "verses": 1})
        chapters[i + 1] = {1: [(1, SAMPLE)]}
        source.append((usfm, SAMPLE))
    files = {"books": books, "chapters": chapters, "source": source}
    if mutate:
        mutate(files)
    return files


def _setv(files, n, text, ch=1, v=1):
    files["chapters"][n] = {ch: [(v, text)]}


def _setall(files, text):
    for n in list(files["chapters"]):
        files["chapters"][n] = {1: [(1, text)]}
    files["source"] = [(usfm, text) for usfm, _ in files["source"]]


def _usfx_source(source, chapters=None):
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<usfx>"]
    for bid, text in source:
        out.append(f'<book id="{bid}"><h>Libro {bid}</h>')
        rows = (chapters or {}).get(bid) or [(1, text)]
        ch = 1
        out.append('<c id="1"/>')
        for v, t in rows:
            if v == 1 and ch > 1:
                out.append(f'<c id="{ch}"/>')
                ch += 1
            out.append(f'<v id="{v}"/>{t}<ve/>')
        out.append("</book>")
    out.append("</usfx>")
    return "\n".join(out)


def _write_fixture(root, files, disclosure_entries=()):
    os.makedirs(root, exist_ok=True)
    for n, chapters in files["chapters"].items():
        payload = {str(ch): [{"v": v, "text": t} for v, t in rows]
                   for ch, rows in chapters.items()}
        with open(os.path.join(root, f"{n}.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
    with open(os.path.join(root, "books.json"), "w", encoding="utf-8") as fh:
        json.dump(files["books"], fh, ensure_ascii=False)
    canon = [dict(b) for b in files["books"]]
    cpath = os.path.join(os.path.dirname(root), os.path.basename(root) + "-canon.json")
    with open(cpath, "w", encoding="utf-8") as fh:
        json.dump(canon, fh, ensure_ascii=False)
    spath = os.path.join(os.path.dirname(root), os.path.basename(root) + "-src.usfx.xml")
    with open(spath, "w", encoding="utf-8") as fh:
        fh.write(_usfx_source(files["source"],
                              files.get("source_chapters")))
    with open(os.path.join(root, "DISCLOSURE.json"), "w", encoding="utf-8") as fh:
        json.dump({"language": "fixture", "primary_source":
                   os.path.basename(spath), "donor": None, "policy": "fixture",
                   "entries": list(disclosure_entries)}, fh, ensure_ascii=False)
    tot_ch = sum(len(c) for c in files["chapters"].values())
    tot_v = sum(len(rows) for c in files["chapters"].values() for rows in c.values())
    report = {"lang": os.path.basename(root), "format": "usfx", "source": spath,
              "books": [{"n": i + 1, "id": USFM_ORDER[i], "name": "Libro",
                         "chapters": len(files["chapters"].get(i + 1, {})),
                         "verses": sum(len(x) for x in files["chapters"].get(i + 1, {}).values())}
                        for i in range(66)],
              "total_chapters": tot_ch, "total_verses": tot_v, "flags": [],
              "native_names": 66, "english_name_fallback": [],
              "disclosure": list(disclosure_entries)}
    with open(os.path.join(root, "build-report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False)
    return spath, cpath


def selftest():
    base = "/tmp/opencode"
    os.makedirs(base, exist_ok=True)
    root = os.path.join(base, f"verify_translation.selftest.{os.getpid()}")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    cases = []

    def run(name, mutate=None, disclosure=(), patch_report=None, canon_rows=None,
            **_ignored):
        d = os.path.join(root, name)
        files = _fixture(mutate)
        spath, cpath = _write_fixture(d, files, disclosure_entries=disclosure)
        if patch_report:
            rp = os.path.join(d, "build-report.json")
            data = json.load(open(rp, encoding="utf-8"))
            patch_report(data)
            json.dump(data, open(rp, "w", encoding="utf-8"))
        rows = canon_rows if canon_rows is not None else \
            json.load(open(cpath, encoding="utf-8"))
        return d, spath, run_verification(d, source=spath, fmt="auto",
                                          canon_rows=rows, top=3)

    def case(name, expect=(), forbid=(), **kw):
        d, _s, res = run(name, **kw)
        codes = {f["check"] for f in res.findings if f["severity"] != "info"}
        missing = [e for e in expect if e not in codes]
        present = [f_ for f_ in forbid if f_ in codes]
        ok = not missing and not present
        detail = f"non-info findings={sorted(codes)} exit={res.exit_code()}"
        if missing:
            detail = f"EXPECTED {missing} but got {sorted(codes)}"
        elif present:
            detail = f"UNEXPECTED {present} in {sorted(codes)}"
        cases.append((name, ok, detail))
        return res

    # 0. a valid build must produce NO findings at all (no false positives)
    case("clean")
    # 1. doubled verse: detector fires AND the source classifies it as the
    #    converter's duplication (not a repeat that exists in the edition)
    def _dbl(f):
        _setv(f, 1, SAMPLE + " " + SAMPLE)
    res = case("doubled", expect=("doubled_text", "roundtrip"), mutate=_dbl)
    ok = (res.stats["doubled"]["classified"].get("converter_double") == 1 and
          res.stats["roundtrip"]["classes"].get("doubled") == 1)
    cases.append(("doubled_classified", ok,
                  f"classified={res.stats['doubled']['classified']} "
                  f"roundtrip={res.stats['roundtrip']['classes']}"))
    # 2. a repeat that IS in the source edition must not be blamed on anybody
    def _rep(f):
        _setv(f, 1, SAMPLE + " " + SAMPLE)
        f["source"][0] = (f["source"][0][0], SAMPLE + " " + SAMPLE)
    res = case("edition_repeat", expect=("doubled_text",), forbid=("missing_verses",),
               severity={"doubled_text": "warn"}, mutate=_rep)
    ok = res.stats["doubled"]["classified"].get("edition_repeat") == 1
    cases.append(("edition_repeat_classified", ok,
                  f"classified={res.stats['doubled']['classified']}"))
    # 3. verse present in the source but absent from the build
    case("missing_verse", expect=("missing_verses",),
         mutate=lambda f: f["chapters"].__setitem__(1, {}))
    # 4. forbidden tokens
    case("forbidden_brace", expect=("forbidden_tokens",),
         mutate=lambda f: _setv(f, 1, SAMPLE + " {added}"))
    case("forbidden_tilde", expect=("forbidden_tokens",),
         mutate=lambda f: _setv(f, 1, SAMPLE + " ~word~"))
    case("forbidden_pilcrow", expect=("forbidden_tokens",),
         mutate=lambda f: _setv(f, 1, SAMPLE + " ¶"))
    case("forbidden_backslash", expect=("forbidden_tokens",),
         mutate=lambda f: _setv(f, 1, SAMPLE + " \\add word\\add*"))
    case("control_char", expect=("forbidden_tokens",),
         mutate=lambda f: _setv(f, 1, SAMPLE + "\x07"))
    case("c1_control", expect=("forbidden_tokens",),
         mutate=lambda f: _setv(f, 1, SAMPLE + "\u0092"))
    # 5. surviving markup
    case("entity_residue", expect=("markup_residue",),
         mutate=lambda f: _setv(f, 1, "Dios dijo: &quot;haga luz&quot;"))
    case("tag_residue", expect=("markup_residue",),
         mutate=lambda f: _setv(f, 1, "Dios dijo <q>haga luz</q>"))
    # 6. `short` slug safety (NETdir:// URL segments)
    case("slug_nonascii", expect=("short_slug",),
         mutate=lambda f: f["books"][0].__setitem__("short", "Génesis"))
    case("slug_space", expect=("short_slug",),
         mutate=lambda f: f["books"][0].__setitem__("short", "Ge nes"))
    case("slug_slash", expect=("short_slug",),
         mutate=lambda f: f["books"][0].__setitem__("short", "Ge/nes"))
    case("slug_empty", expect=("short_slug",),
         mutate=lambda f: f["books"][0].__setitem__("short", ""))
    case("slug_duplicate", expect=("short_slug",),
         mutate=lambda f: f["books"][1].__setitem__("short", "Bk01"))
    # 7. gaps: undisclosed fails, disclosed does not
    case("empty_verse", expect=("undisclosed_gap",),
         mutate=lambda f: _setv(f, 1, ""))
    case("undisclosed_marker", expect=("undisclosed_gap",),
         mutate=lambda f: _setv(f, 1, "<aaa part missing>"))
    case("undisclosed_inline_marker", expect=("undisclosed_gap",),
         mutate=lambda f: _setv(f, 1, SAMPLE + " [missing in this edition]"))
    case("disclosed_gap", forbid=("undisclosed_gap",),
         mutate=lambda f: _setv(f, 1, ""),
         disclosure=({"book": "GEN", "chapter": 1, "verse": 1,
                      "kind": "unfilled_gap"},))
    case("disclosed_marker_text", forbid=("undisclosed_gap",),
         mutate=lambda f: _setv(f, 1, GAP_MARK),
         disclosure=({"book": "GEN", "chapter": 1, "verse": 1,
                      "kind": "unfilled_gap"},))
    # 8. structure
    case("chapter_gap", expect=("structure",),
         mutate=lambda f: f["chapters"].__setitem__(1, {1: [(1, SAMPLE)], 3: [(1, SAMPLE)]}))
    case("verse_duplicate", expect=("structure",),
         mutate=lambda f: f["chapters"].__setitem__(1, {1: [(1, SAMPLE), (1, SAMPLE)]}))
    case("verse_gap", expect=("structure",),
         mutate=lambda f: f["chapters"].__setitem__(1, {1: [(1, SAMPLE), (3, SAMPLE)]}))
    # a gap the SOURCE edition also has is faithful, so it must be a warning
    # under its own code and must NOT be reported as a structural defect
    def _edition_gap(f):
        f["chapters"][1] = {1: [(1, SAMPLE), (3, SAMPLE)]}
        f["source_chapters"] = {"GEN": [(1, SAMPLE), (3, SAMPLE)]}
        f["books"][0]["verses"] = 2
    case("verse_gap_in_source", expect=("edition_versification",),
         forbid=("structure",), mutate=_edition_gap)
    case("metadata_verses_mismatch", expect=("structure",),
         mutate=lambda f: f["books"][0].__setitem__("verses", 99))
    case("metadata_chapters_mismatch", expect=("structure",),
         mutate=lambda f: f["books"][0].__setitem__("chapters", 99))
    case("book_file_missing", expect=("structure",),
         mutate=lambda f: f["chapters"].pop(3))
    # 9. script / language fingerprint
    case("wrong_script_english_in_russian", expect=("script",),
         patch_report=lambda d: d.__setitem__("lang", "rus"),
         mutate=lambda f: _setall(f, "In the beginning God created the heaven and "
                                     "the earth, and the earth was without form "
                                     "and void, and there was darkness upon the "
                                     "face of the deep."))
    case("correct_script_russian", forbid=("script",),
         patch_report=lambda d: d.__setitem__("lang", "rus"),
         mutate=lambda f: _setall(f, "В начале сотворил Бог небо и землю, и земля "
                                     "была безвидна и пуста, и тьма была над "
                                     "бездною."))
    # 10. encoding
    case("fffd", expect=("encoding",),
         mutate=lambda f: _setv(f, 1, SAMPLE + " \ufffd"))
    case("decomposed_text", expect=("encoding",),
         patch_report=lambda d: d.__setitem__("lang", "spa"),
         mutate=lambda f: _setv(f, 1, "El Esp\u0301ritu de Dios se mov\u00eda."))
    # 11. round-trip wording difference that is NOT a doubling
    case("wording_delta", expect=("roundtrip",),
         mutate=lambda f: _setv(f, 2, "En el principio creo Dios los cielos."))
    # 12. report reconciliation
    case("report_total_mismatch", expect=("report_reconciliation",),
         patch_report=lambda d: d.__setitem__("total_verses", 999))
    case("report_book_mismatch", expect=("report_reconciliation",),
         patch_report=lambda d: d["books"][0].__setitem__("verses", 42))
    case("report_c1_claim", expect=("report_reconciliation",),
         patch_report=lambda d: d.__setitem__("sanitize", {"c1_mojibake": 5}),
         mutate=lambda f: _setv(f, 1, SAMPLE + " \u0092"))
    # 13. provenance: build claims a different source than the one verified
    case("provenance_mismatch", expect=("provenance",),
         patch_report=lambda d: d.__setitem__("source", "/somewhere/other.xml"))

    # 14. the doubled-vs-source classification must never blame the edition
    #     when the built text is NOT a repeat of the source verse
    case("doubled_but_source_differs", expect=("doubled_text",),
         mutate=lambda f: (_setv(f, 1, SAMPLE + " " + SAMPLE),
                           f["source"].__setitem__(0, (f["source"][0][0], "Otro texto."))))

    # 15. dialect sniffing
    sniff, detail = True, []
    for name, text, want in (
        ("sniff-usfx.xml", '<?xml version="1.0"?><usfx><book id="GEN"/></usfx>', "usfx"),
        ("sniff-zefania.xml", "<XMLBIBLE><BIBLEBOOK bnumber='1'/></XMLBIBLE>", "zefania"),
        ("sniff-osis.xml", "<osis><osisText><div type='book' osisID='Gen'/></osisText></osis>", "osis"),
        ("sniff-sjson.json", '{"books": []}', "sjson"),
    ):
        p = os.path.join(root, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        got = detect_format(p)
        if got != want:
            sniff = False
            detail.append(f"{want}->{got}")
    cases.append(("format_sniff", sniff, " ".join(detail) or "usfx/zefania/osis/sjson"))

    # 16. exit-code ladder 0 / 2 / 1
    r = Result.__new__(Result)
    r.findings = []
    r.build = None
    ok = r.exit_code() == 0
    r.findings = [{"check": "x", "severity": "warn", "title": "t"}]
    ok = ok and r.exit_code() == 2
    r.findings.append({"check": "y", "severity": "fail", "title": "t"})
    ok = ok and r.exit_code() == 1
    cases.append(("exit_codes", ok, "clean=0 warnings=2 failures=1"))

    # 17. exact_double_split must agree with the literal "t[:k]+t[k:]" scan
    ok, detail = True, []
    # exact_double_split ignores repeats shorter than 4 chars (a 1-char "half"
    # is not a doubled verse), so the probe starts at len 4.
    for t in ("abab", "abcabc", "aaaa", "ababab", "x" * 41, "a" * 5, SAMPLE * 2,
              SAMPLE, ""):
        brute = None
        for k in range(1, len(t)):
            if t[:k] == t[k:]:
                brute = k
                break
        got = exact_double_split(t)
        if got != brute:
            ok = False
            detail.append(f"{t[:12]!r}:{got}!={brute}")
    cases.append(("exact_double_split", ok, " ".join(detail) or "matches brute force"))

    # 17b. SHORT duplicated verse with a seam separator: every length-based
    #      heuristic misses it unless whitespace is squashed first.  This is the
    #      real kor LEV 11:15 case ('까마귀 종류와 까마귀 종류와').
    def _shortdbl(f):
        f["chapters"][1] = {1: [(1, "까마귀 종류와 까마귀 종류와")]}
        f["source"][0] = (f["source"][0][0], "까마귀 종류와")
    res = case("short_spaced_double", expect=("doubled_text", "roundtrip"),
               mutate=_shortdbl)
    ok = (res.stats["doubled"]["classified"].get("converter_double") == 1 and
          res.stats["roundtrip"]["classes"].get("doubled") == 1 and
          not res.stats["roundtrip"]["classes"].get("text"))
    cases.append(("short_spaced_double_classified", ok,
                  f"classified={res.stats['doubled']['classified']} "
                  f"roundtrip={res.stats['roundtrip']['classes']}"))

    # 17b-2. inline <note>: the converter emits the pre-markup text and then
    #      the whole verse, so the built string is the source verse with its
    #      opening run repeated.  Must be named, not filed as a wording delta.
    def _prefixrep(f):
        whole = "Agua Hidekel Tigris fluye Asiria. CuartaAsia."
        _setv(f, 1, "Agua Hidekel " + whole)
        f["source"][0] = (f["source"][0][0], whole)
    res = case("prefix_repeat", expect=("roundtrip",), mutate=_prefixrep)
    ok = res.stats["roundtrip"]["classes"].get("prefix_repeat") == 1
    cases.append(("prefix_repeat_classified", ok,
                  f"roundtrip={res.stats['roundtrip']['classes']}"))

    # 17b-3. an empty source verse the build fills with a placeholder is a FILL
    #      (disclosure is check_gaps' job), and its mirror is an ERASURE.
    case("filled_verse", expect=("roundtrip", "undisclosed_gap"),
         mutate=lambda f: (_setv(f, 1, "<missing in this edition>"),
                           f["source"].__setitem__(0, (f["source"][0][0], ""))))
    case("erased_verse", expect=("roundtrip", "undisclosed_gap"),
         mutate=lambda f: _setv(f, 1, ""))

    # 17c. a source whose verses cannot be placed in a canonical book must not
    #      be accepted as ground truth.
    d = os.path.join(root, "unplaced-source")
    os.makedirs(d, exist_ok=True)
    bad_src = os.path.join(d, "src")
    with open(bad_src, "w", encoding="utf-8") as fh:
        fh.write("<osis><osisText>"
                 "<verse osisID='Gen.1.1'>Hola</verse>"
                 "<verse osisID='Gen.1.2'>Adios</verse>"
                 "</osisText></osis>")
    _files = _fixture()
    _spath, cpath = _write_fixture(os.path.join(root, "unplaced-build"), _files)
    res = run_verification(os.path.join(root, "unplaced-build"),
                           source=bad_src, fmt="auto",
                           canon_rows=json.load(open(cpath, encoding="utf-8")),
                           top=3)
    codes = {f["check"] for f in res.findings if f["severity"] != "info"}
    cases.append(("unplaced_source_verse", "source_parse" in codes,
                  f"non-info findings={sorted(codes)}"))

    # 18. source parsers really are independent of the build (all four dialects
    #     round-trip their own fixture through the shared pipeline)
    def _mk(tag, body, fmt):
        d = os.path.join(root, "dialect-" + fmt)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "src")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        books, names, stats = parse_source(p, fmt, canon=None,
                                           index=build_name_index(None))
        return sum(len(r) for m in books.values() for r in m.values()), sorted(books)
    zf = ("<XMLBIBLE><BIBLEBOOK bnumber='1' bname='Genesis'><CHAPTER cnumber='1'>"
          "<CAPTION vref='1'>Genesis</CAPTION><VERS vnumber='1'>Hola</VERS>"
          "<VERS vnumber='2'>Adios</VERS></CHAPTER></BIBLEBOOK></XMLBIBLE>")
    os_ = ("<osis><osisText><div type='book' osisID='Gen'><title>Genesis</title>"
           "<chapter osisID='Gen.1'><verse osisID='Gen.1.1'>Hola</verse>"
           "<verse osisID='Gen.1.2'>Adios</verse></chapter></div></osisText></osis>")
    # The trap that hid a real bug: USFX <c> is SELF-CLOSING, so the last verse of
    # a chapter is still pending when the next <c/> opens.  Two chapters are
    # needed to exercise it -- one chapter per book would pass either way.
    uf = ("<usfx><book id='GEN'><h>Genesis</h>"
          "<c id='1'/><v id='1'>Hola</v><v id='2'>Adios</v>"
          "<c id='2'/><v id='1'>Tercer</v>"
          "</book></usfx>")
    # sjson: inline markup inside the verse STRING, apparatus dropped.
    sj = {"books": [{"name": "Genesis", "chapters": [{"chapter": 1, "verses": [
                        {"verse": 1, "text": "Hola <transChange>added</transChange>"},
                        {"verse": 2, "text": "Ad&amp;ios"}]}]}]}
    ok = True
    detail = []
    try:
        n1, b1 = _mk("z", zf, "zefania")
        n2, b2 = _mk("o", os_, "osis")
        n3, b3 = _mk("u", uf, "usfx")
        d4 = os.path.join(root, "dialect-sjson")
        os.makedirs(d4, exist_ok=True)
        p4 = os.path.join(d4, "src")
        with open(p4, "w", encoding="utf-8") as fh:
            json.dump(sj, fh)
        idx4 = build_name_index([{"name": "Genesis", "short": "Gen"}])
        books4, _, _ = parse_source(p4, "sjson", index=idx4)
        rows4 = [t for _, t in books4["GEN"][1]]
        ok = (n1 == 2 and b1 == ["GEN"] and n2 == 2 and b2 == ["GEN"]
              and n3 == 3 and b3 == ["GEN"]
              and rows4 == ["Hola", "Ad&ios"])
        detail = (f"zefania={n1}{b1} osis={n2}{b2} "
                  f"usfx-selfclosing-c={n3}{b3} sjson={rows4}")
    except Exception as exc:
        ok = False
        detail = f"{type(exc).__name__}: {exc}"
    cases.append(("xml_dialects", ok, detail))

    print("verify_translation --selftest")
    width = max(len(n) for n, _, _ in cases)
    failed = 0
    for name, ok, detail in cases:
        if not ok:
            failed += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name.ljust(width)}  {detail}")
    shutil.rmtree(root, ignore_errors=True)
    if failed:
        print(f"\n*** SELFTEST FAILED: {failed}/{len(cases)} case(s) did not "
              f"behave as required ***")
        return 1
    print(f"\nall {len(cases)} selftest cases passed")
    return 0





if __name__ == "__main__":
    sys.exit(main())
