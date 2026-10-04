#!/usr/bin/env python3
r"""Convert a USFM Bible translation into EXALTED's canonical JSON layout.

Reads an eBible/BibleAquifer USFM release (one .usfm per book, \h = book
name, \c = chapter, \v = verse) and writes the same shape the KJV source
already uses, so gen-exalted-reds.py needs no per-language code:

    translations/<lang>/<n>.json   { "<chapter>": [ {"v": 1, "text": ...} ] }
    translations/<lang>/books.json  [ {n, name, short, chapters, verses} ]

Source files are only ever READ. Markup is stripped here, once, at ingest --
never from the user's Bible files.

Word/added-word markers (\w .. \w*, \add .. \add*) are unwrapped (their text
is kept: \add marks translator-supplied words, which are scripture, not
apparatus). Chapter/paragraph markers are dropped. Strong's numbers and any
other attributes are removed.

Validation is deliberately strict, because a silent verse drop would ship a
Bible with holes in it:
  * exactly 66 books, in canonical USFM order (explicit id table below)
  * per-book chapter count matches the canonical KJV books.json
  * 1189 chapters / N verses, N reported so the generator can assert it
  * no token the redscript encoder uses ({ } ~) and no pilcrow survives
"""
import argparse
import json
import os
import re
import sys

# Canonical Protestant 66 in USFM order. The converter asserts this sequence so
# a re-ordered or partial source can never be silently accepted.
USFM_ORDER = [
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL", "MAT",
    "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP",
    "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE",
    "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
]

# Attributes on a marker: |strong="H0430" etc.
ATTR = re.compile(r'\|[^|]*?(?=\s|\Z)')
# Any USFM marker, with or without the closing '*'. Only \w and \add are
# unwrapped (content kept); everything else is structural and dropped.
# The leading [+-] matters: eBible emits word-part markers such as \+w and \+w*
# (fragments of one word split across attributes), which must not leak.
MARKER = re.compile(r"\\[+\-a-zA-Z0-9]+\*?")

FORBIDDEN = ("{", "}", "~", "¶")


def clean(raw):
    """Strip USFM markup from one verse body and normalise whitespace."""
    text = ATTR.sub("", raw)
    text = MARKER.sub("", text)
    # Control chars / NBSP -> plain space, then collapse runs.
    text = text.replace(" ", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if "\\" in text:
        raise ValueError(f"unconsumed USFM marker in verse: {text[:120]!r}")
    return text


def parse_book(path):
    """Return (usfm_id, name, short, {chapter: [(verse, text)]})."""
    usfm_id = name = short = None
    chapters = {}
    cur_ch = None
    cur_v = None
    cur_parts = []

    def flush():
        if cur_ch is not None and cur_v is not None:
            chapters.setdefault(cur_ch, []).append((cur_v, clean(" ".join(cur_parts))))

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("//"):
                continue
            m = re.match(r"\\id\s+(\S+)", line)
            if m and usfm_id is None:
                usfm_id = m.group(1)
                continue
            m = re.match(r"\\h\s+(.*)", line)
            if m and name is None:
                name = clean(m.group(1))
                continue
            m = re.match(r"\\toc2\s+(.*)", line)
            if m and short is None:
                short = clean(m.group(1))
                continue
            m = re.match(r"\\c\s+(\d+)", line)
            if m:
                flush()
                cur_ch, cur_v, cur_parts = int(m.group(1)), None, []
                continue
            m = re.match(r"\\v\s+(\d+)\s*(.*)", line)
            if m:
                flush()
                cur_v, cur_parts = int(m.group(1)), [m.group(2)]
                continue
            if cur_v is not None and line.strip():
                cur_parts.append(line)
    flush()
    return usfm_id, name, short, chapters


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("usfm_dir", help="dir of extracted .usfm files")
    ap.add_argument("--out", required=True, help="output dir, e.g. translations/es")
    ap.add_argument("--canon", default=None,
                    help="canonical books.json to validate chapter counts against "
                         "(default: cet/EXALTED/data/books.json)")
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    canon_path = args.canon or os.path.join(root, "cet", "EXALTED", "data", "books.json")

    files = sorted((f for f in os.listdir(args.usfm_dir) if f.lower().endswith(".usfm")),
                   key=lambda f: int(re.match(r"(\d+)", f).group(1)))
    if len(files) != 66:
        sys.exit(f"expected 66 .usfm files, found {len(files)}")

    canon = json.load(open(canon_path, encoding="utf-8"))
    if len(canon) != 66:
        sys.exit(f"canonical books.json has {len(canon)} books, expected 66")

    os.makedirs(args.out, exist_ok=True)
    books_out = []
    total_ch = total_v = 0
    seen_ids = []

    if len(files) != len(USFM_ORDER) or len(files) != len(canon):
        sys.exit(
            f"input/canon length mismatch: {len(files)} files, "
            f"{len(USFM_ORDER)} USFM_ORDER entries, {len(canon)} books"
        )

    for n, (fname, want_id, cref) in enumerate(
        zip(files, USFM_ORDER, canon, strict=True), start=1
    ):
        path = os.path.join(args.usfm_dir, fname)
        usfm_id, name, short, chapters = parse_book(path)
        if usfm_id != want_id:
            sys.exit(f"book {n}: expected USFM id {want_id}, got {usfm_id} ({fname})")
        seen_ids.append(usfm_id)
        if not name:
            sys.exit(f"book {n} {usfm_id}: no \\h book name")
        if not short:
            short = name
        if len(chapters) != int(cref["chapters"]):
            sys.exit(f"book {n} {usfm_id} ({name}): {len(chapters)} chapters, "
                     f"canonical canon says {cref['chapters']}")

        payload = {}
        verses_here = 0
        for ch in sorted(chapters):
            rows = []
            for num, text in chapters[ch]:
                for tok in FORBIDDEN:
                    if tok in text:
                        sys.exit(f"{usfm_id} {ch}:{num} contains forbidden token {tok!r}")
                rows.append({"v": num, "text": text})
            payload[str(ch)] = rows
            verses_here += len(rows)
        if verses_here != int(cref["verses"]):
            sys.exit(f"book {n} {usfm_id} ({name}): {verses_here} verses, "
                     f"canonical canon says {cref['verses']}")

        with open(os.path.join(args.out, f"{n}.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
            fh.write("\n")

        books_out.append({"n": n, "name": name, "short": short,
                          "chapters": len(chapters), "verses": verses_here})
        total_ch += len(chapters)
        total_v += verses_here

    with open(os.path.join(args.out, "books.json"), "w", encoding="utf-8") as fh:
        json.dump(books_out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    print(f"converted {len(books_out)} books -> {args.out}: "
          f"{total_ch} chapters, {total_v} verses")
    print(f"ids ok: {seen_ids[0]}..{seen_ids[-1]}")


if __name__ == "__main__":
    main()