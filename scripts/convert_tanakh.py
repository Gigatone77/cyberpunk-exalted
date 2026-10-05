#!/usr/bin/env python3
"""Convert the Tanach.us Unicode/XML Leningrad Codex (UXLC) into EXALTED's
canonical per-book JSON layout.

WHY A SEPARATE CONVERTER
========================
scripts/convert_bible.py handles whole-Bible *translations* of the 66-book
canon: its book list, its chapter-boundary audit and its output loop are all
keyed to USFM_ORDER and to a hard `len(books) != 66`. The Tanakh is not a
translation of that canon -- it is a DIFFERENT CANON: 39 books, no New
Testament, ending at Malachi. Threading a 39-book source through a 66-book
pipeline would have meant weakening every one of those assumptions for every
existing language. So this is a sibling converter that emits the SAME output
contract (books.json + <n>.json + build-report.json), which
scripts/gen-exalted-reds.py and scripts/build_lang.sh then consume unchanged.

SOURCE + LICENCE
================
Tanach.us Unicode/XML Leningrad Codex (UXLC), Tanach.us Inc.
  archive   http://www.tanach.us/Books/Tanach.xml.zip
  licence   "All biblical Hebrew text, in any format, may be viewed or copied
             without restriction." (shipped inside the archive as License.html)
  version   UXLC 2.5, build 27.6, 1 Apr 2026
This is the root format of tanach.us: the XML book files are the basis for
every other format the site serves. The plain Books/<Name>.xml files are used;
the five *.DH.xml files are Documentary-Hypothesis variants of the Torah books
and are deliberately EXCLUDED -- EXALTED ships the received text, not a
source-critical apparatus.

Reading conventions encoded here (each recorded in the build report):
  * ketiv/qere -- where a <k> (ketiv) / <q> (qere) pair appears, the QERE is
    printed. That is what a reading edition prints; the defective ketiv is not
    part of the read text.
  * <x> -- carries the letter that must be joined to the preceding one with no
    space (e.g. <w>be<x>t</x>eden</w>). Descendant-text concatenation handles
    it; no special-casing needed.
  * <pe> / <samekh> -- open / closed paragraph markers, i.e. real Masoretic
    structure. These are STRIPPED, not emitted: gen-exalted-reds.py forbids the
    characters "{", "}" and "~" in source text because it owns that syntax
    itself, and hard-wraps every verse on its own. Injecting "{~}" here aborted
    the generator outright. Their counts are recorded in the build report and
    in DISCLOSURE.json so the loss of structure is visible rather than silent.
    The WORDING is untouched -- only the paragraph division is not carried.
  * cantillation and nikkud are kept verbatim. Nothing is stripped, reflowed or
  "corrected"; the text ships as the edition has it.

PER-BOOK COUNTS ARE ASSERTED, NOT REPORTED
===========================================
The swe-swedish.osis.xml build shipped 7 New Testament books under the wrong
book name while every total, chapter count and file count still matched, and
the build report had actually flagged it -- as "NOTE ... (may be legitimate
versification)", wording that is indistinguishable from a real tradition. A
variance note with no power to tell tradition from corruption is worse than no
check, because it reads as a cleared item.

Here the Masoretic per-book chapter and verse counts are standard and
well-attested, so any deviation is an ERROR and aborts the build. The
convention difference that trips people up is documented below and asserted at
the TOTAL level, where it belongs.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON_BOOKS = os.path.join(REPO, "cet", "EXALTED", "data", "books.json")

# Tanakh books in Masoretic order -> canonical chapter/verse counts.
# These are the standard Masoretic per-book counts. Numbers 4 (1289), 8 (811),
# 11 (817), 13 (943), 16 (73), 19 (2527), 20 (915), 23 (1291), 29 (1070),
# 33 (222), 37 (405) are the Hebrew counts; they differ from the English
# chapter/verse division in exactly the places the Hebrew text differs, and
# that is correct here rather than a defect to reconcile.
MASORETIC = {
    1: ("Genesis", 50, 1533), 2: ("Exodus", 40, 1213), 3: ("Leviticus", 27, 859),
    4: ("Numbers", 36, 1289), 5: ("Deuteronomy", 34, 959), 6: ("Joshua", 24, 658),
    7: ("Judges", 21, 618), 8: ("1 Samuel", 31, 811), 9: ("2 Samuel", 24, 695),
    10: ("1 Kings", 22, 817), 11: ("2 Kings", 25, 719), 12: ("Isaiah", 66, 1291),
    13: ("Jeremiah", 52, 1364), 14: ("Ezekiel", 48, 1273), 15: ("Hosea", 14, 197),
    16: ("Joel", 4, 73), 17: ("Amos", 9, 146), 18: ("Obadiah", 1, 21),
    19: ("Jonah", 4, 48), 20: ("Micah", 7, 105), 21: ("Nahum", 3, 47),
    22: ("Habakkuk", 3, 56), 23: ("Zephaniah", 3, 53), 24: ("Haggai", 2, 38),
    25: ("Zechariah", 14, 211), 26: ("Malachi", 3, 55), 27: ("Psalms", 150, 2527),
    28: ("Proverbs", 31, 915), 29: ("Job", 42, 1070), 30: ("Song of Songs", 8, 117),
    31: ("Ruth", 4, 85), 32: ("Lamentations", 5, 154), 33: ("Ecclesiastes", 12, 222),
    34: ("Esther", 10, 167), 35: ("Daniel", 12, 357), 36: ("Ezra", 10, 280),
    37: ("Nehemiah", 13, 405), 38: ("1 Chronicles", 29, 943),
    39: ("2 Chronicles", 36, 822),
}

MASORETIC_CHAPTERS = 929
MASORETIC_VERSES = 23213

# Source book title -> canonical books.json title. Matched BY NAME, never by
# index: the Tanakh numbers Malachi 26 while the KJV canon numbers it 39, so
# positional mapping would have silently mislabelled 13 books.
TITLE_ALIAS = {
    "song of songs": "song of solomon",   # tanach.us name vs KJV name
}

SKIP_FILES = {"TanachHeader.xml", "TanachIndex.xml"}
DH_SUFFIX = ".DH.xml"


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").lower()
    return re.sub(r"[^a-z0-9 ]+", " ", t).split() and " ".join(
        re.sub(r"[^a-z0-9 ]+", " ", t.lower()).split()) or ""


def canon_short_map():
    """canonical title -> (short, chapters, verses) from the shipped books.json."""
    with open(CANON_BOOKS, encoding="utf-8") as fh:
        rows = json.load(fh)
    return {norm(r["name"]): (r["short"], r["chapters"], r["verses"]) for r in rows}


def resolve_books(src_dir):
    files = []
    for f in sorted(glob.glob(os.path.join(src_dir, "Books", "*.xml"))):
        base = os.path.basename(f)
        if base in SKIP_FILES or base.endswith(DH_SUFFIX):
            continue
        files.append(f)
    return files


def book_payload(book_el):
    """Return {chapter: [ {v, text} ]} for one <book> element."""
    out = {}
    pe = samekh = kq = 0
    for c in book_el.findall("c"):
        cn = int(c.get("n"))
        rows = []
        for v in c.findall("v"):
            vn = int(v.get("n"))
            parts = []
            for child in v:
                tag = child.tag
                if tag == "w":
                    # itertext() picks up the inline <x> join letters.
                    parts.append("".join(child.itertext()))
                elif tag == "q":
                    kq += 1
                    parts.append("".join(child.itertext()))
                elif tag == "k":
                    kq += 1  # ketiv: deliberately not printed
                elif tag == "pe":
                    # counted, not emitted -- see the module docstring
                    pe += 1
                elif tag == "samekh":
                    samekh += 1
                elif tag in ("s", "reversednun"):
                    parts.append("".join(child.itertext()))
            text = " ".join(p for p in parts if p)
            text = re.sub(r"[ \t]+", " ", text).strip()
            rows.append({"v": vn, "text": text})
        out[cn] = rows
    return out, {"pe": pe, "samekh": samekh, "ketiv_qere": kq}


def convert(src_dir, out_dir, lang="heb", note=()):
    files = resolve_books(src_dir)
    if len(files) != 39:
        sys.exit(f"expected 39 Tanakh book files, found {len(files)} in {src_dir}")

    cmap = canon_short_map()
    books, report_flags = [], []
    total_ch = total_v = 0
    stats = {"pe": 0, "samekh": 0, "ketiv_qere": 0}
    disclosure = [{"kind": "editorial_note",
                   "note": "Tanakh (39 books, no New Testament). Text is the "
                           "Tanach.us UXLC; qere printed where ketiv/qere differ."},
                  {"kind": "editorial_note",
                   "note": "Masoretic open/closed paragraph markers (pe/samekh) "
                           "are not carried: EXALTED reserves { } ~ for its own "
                           "line syntax and wraps verses itself. Wording is "
                           "verbatim; only the paragraph division is dropped."}]
    for f in files:
        root = ET.parse(f).getroot()
        b = root.find("tanach/book")
        if b is None:
            sys.exit(f"{f}: no tanach/book element")
        names = b.find("names")
        number = int(names.find("number").text)
        title = names.find("name").text
        hebrew = names.find("hebrewname").text

        canon_name = norm(title)
        key = TITLE_ALIAS.get(canon_name, canon_name)
        if key not in cmap:
            sys.exit(f"{f}: {title!r} has no canonical books.json match "
                     f"(looked for {key!r})")
        short, canon_ch, canon_v = cmap[key]

        payload, st = book_payload(b)
        for k in stats:
            stats[k] += st[k]

        ch_count = len(payload)
        v_count = sum(len(r) for r in payload.values())
        want_name, want_ch, want_v = MASORETIC[number]

        if title != want_name:
            sys.exit(f"{title!r}: Masoretic order says book {number} is "
                     f"{want_name!r}")
        if ch_count != want_ch:
            sys.exit(f"{title}: {ch_count} chapters, Masoretic {want_ch}")
        if v_count != want_v:
            sys.exit(f"{title}: {v_count} verses, Masoretic {want_v}")
        if [n for n, r in payload.items()] != list(range(1, ch_count + 1)):
            sys.exit(f"{title}: chapter numbers not contiguous 1..{ch_count}")
        for cn, rows in payload.items():
            nums = [r["v"] for r in rows]
            if nums != list(range(1, len(nums) + 1)):
                sys.exit(f"{title} {cn}: verse numbers not contiguous 1..{len(nums)}")

        # Hebrew chapter division vs the English/KJV one: recorded, never
        # reconciled. The language's tradition governs its own versification.
        if ch_count != canon_ch:
            disclosure.append({
                "kind": "chapter_boundary", "book": short,
                "usfm": short, "name": hebrew,
                "chapters_in_source": ch_count, "chapters_canonical": canon_ch,
            })
        if v_count != canon_v:
            disclosure.append({
                "kind": "verse_total", "book": short, "usfm": short,
                "name": hebrew,
                "verses_in_source": v_count, "verses_canonical": canon_v,
            })

        books.append({
            "n": number, "name": hebrew, "short": short,
            "chapters": ch_count, "verses": v_count,
        })
        with open(os.path.join(out_dir, f"{number}.json"), "w",
                  encoding="utf-8", newline="\n") as fh:
            json.dump({str(k): v for k, v in sorted(payload.items())},
                      fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        total_ch += ch_count
        total_v += v_count

    if total_ch != MASORETIC_CHAPTERS:
        sys.exit(f"total chapters {total_ch}, Masoretic {MASORETIC_CHAPTERS}")
    if total_v != MASORETIC_VERSES:
        sys.exit(f"total verses {total_v}, Masoretic {MASORETIC_VERSES}")

    books.sort(key=lambda b: b["n"])
    with open(os.path.join(out_dir, "books.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(books, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    for n in note:
        disclosure.append({"kind": "editorial_note", "note": n})
    report = {
        "lang": lang,
        "format": "uxlc-tanach",
        "canon": "tanakh-39",
        "source": os.path.abspath(src_dir),
        "upstream": {
            "archive": "http://www.tanach.us/Books/Tanach.xml.zip",
            "edition": "Unicode/XML Leningrad Codex (UXLC) 2.5, build 27.6, 1 Apr 2026",
            "licence": "All biblical Hebrew text, in any format, may be viewed "
                       "or copied without restriction. (License.html in archive)",
            "excluded": "Books/*.DH.xml -- Documentary Hypothesis variants of the "
                        "five Torah books; EXALTED ships the received text.",
        },
        "books": books,
        "total_chapters": total_ch,
        "total_verses": total_v,
        "red_verses": 0,
        "flags": report_flags,
        "native_names": sum(1 for b in books if b["name"]),
        "masoretic_assert": {
            "per_book": "enforced (any deviation aborts the build)",
            "total_chapters": MASORETIC_CHAPTERS,
            "total_verses": MASORETIC_VERSES,
        },
        "verse_count_convention": (
            f"This edition counts {MASORETIC_VERSES} verses, the Masoretic "
            f"per-book total. The frequently quoted 23,153 is a different "
            f"convention that merges the final half-verse of several books; "
            f"it is NOT a discrepancy in this text and must not be 'corrected'."
        ),
        "structure": {
            "open_paragraphs_pe": stats["pe"],
            "closed_paragraphs_samekh": stats["samekh"],
            "paragraph_policy": "pe/samekh markers counted and STRIPPED -- "
                                "gen-exalted-reds.py reserves { } ~ for its own "
                                "syntax and hard-wraps verses itself. Wording is "
                                "unaffected; the Masoretic paragraph division is "
                                "not carried into the .reds.",
            "ketiv_qere_pairs": stats["ketiv_qere"],
            "ketiv_qere_policy": "qere printed, defective ketiv omitted",
        },
        "disclosure": disclosure,
        "disclosure_summary": {
            k: sum(1 for d in disclosure if d["kind"] == k)
            for k in {d["kind"] for d in disclosure}
        },
    }
    with open(os.path.join(out_dir, "build-report.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    with open(os.path.join(out_dir, "DISCLOSURE.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(disclosure, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return report


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def selftest(src_dir):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        rep = convert(src_dir, td, "heb")
        assert rep["total_chapters"] == MASORETIC_CHAPTERS, rep["total_chapters"]
        assert rep["total_verses"] == MASORETIC_VERSES, rep["total_verses"]
        assert len(rep["books"]) == 39, len(rep["books"])
        assert rep["native_names"] == 39
        # Slugs must equal the canonical KJV short for the same book, so that
        # /b/<short> stays a valid route in every language.
        cmap = canon_short_map()
        want = {}
        for b in rep["books"]:
            key = norm(MASORETIC[b["n"]][0])
            want[b["n"]] = cmap[TITLE_ALIAS.get(key, key)][0]
        got = {b["n"]: b["short"] for b in rep["books"]}
        assert got == want, (got, want)
        # Every slug must be route-safe (ASCII alnum, <=12).
        for s in got.values():
            assert re.fullmatch(r"[A-Za-z0-9]{1,12}", s), s
        # Genesis 1:1 must round-trip as real pointed Hebrew, not empty.
        # Compare on the consonantal skeleton: nikkud/te'amim are kept in the
        # output, so a bare substring test would miss them.
        g = json.load(open(os.path.join(td, "1.json"), encoding="utf-8"))
        v1 = g["1"][0]["text"]
        skeleton = "".join(
            c for c in unicodedata.normalize("NFD", v1)
            if "א" <= c <= "ת"          # Hebrew LETTERS only (Lo);
            # nikkud (Mn) and te'amim are dropped, so what is left is the
            # consonantal skeleton the word is actually spelled with.
        )
        for word in ("בראשית", "ברא", "אלהים", "השמים", "הארץ"):
            assert word in skeleton, (word, skeleton)
        # The te'amim and the sof pasuq must survive: this is a pointed text.
        assert "׃" in v1, v1
        assert any("֐" <= c <= "ֿ" for c in v1), v1
        # Malachi is book 26 here, NOT 39 -- the canonical-number trap.
        mal = [b for b in rep["books"] if b["name"] == "מלאכי"]
        assert mal and mal[0]["n"] == 26, mal
        print(f"selftest OK: 39 books, {rep['total_chapters']} chapters, "
              f"{rep['total_verses']} verses; Gen 1:1 -> {v1[:40]}...")
        print(f"  ketiv/qere pairs: {rep['structure']['ketiv_qere_pairs']}, "
              f"open par. {rep['structure']['open_paragraphs_pe']}, "
              f"closed par. {rep['structure']['closed_paragraphs_samekh']}")


def main():
    ap = argparse.ArgumentParser(
        description="Convert Tanach.us UXLC Tanakh to EXALTED book JSON.")
    ap.add_argument("src", help="extracted Tanach.xml tree (with Books/)")
    ap.add_argument("--out", help="output dir (books.json + <n>.json + report)")
    ap.add_argument("--lang", default="heb")
    ap.add_argument("--note", action="append", default=[], metavar="TEXT")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--sha256", metavar="ARCHIVE",
                    help="print sha256 of the upstream archive and exit")
    args = ap.parse_args()

    if args.sha256:
        print(sha256(args.sha256))
        return
    if not os.path.isdir(os.path.join(args.src, "Books")):
        sys.exit(f"{args.src}: no Books/ directory")
    if args.selftest:
        selftest(args.src)
        return
    if not args.out:
        sys.exit("--out is required unless --selftest")
    os.makedirs(args.out, exist_ok=True)
    rep = convert(args.src, args.out, args.lang, args.note)
    print(f"[{args.lang}] tanakh-39: {len(rep['books'])} books, "
          f"{rep['total_chapters']} chapters, {rep['total_verses']} verses")
    print(f"[{args.lang}] native book names {rep['native_names']}/39")
    print(f"[{args.lang}] disclosure: {rep['disclosure_summary']}")


if __name__ == "__main__":
    main()