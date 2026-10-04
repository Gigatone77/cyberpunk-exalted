#!/usr/bin/env python3
"""Generate the redscript data module for the EXALTED in-game browser site.

Reads the clean CET data assets (data/books.json + data/kjv/<n>.json) and
emits rescript source under internet/EXALTED/data/. Each chapter becomes one
String literal; verses are joined with the token "{|}"; verse lines (hard
wrapped to WRAP chars so they render even when inkText does not wrap) with
"{~}"; Words of Jesus are wrapped in "{r}...{/r}".

Tokens were chosen because they never occur in the KJV text (asserted below).
No file I/O is available to redscript, so the text ships as script constants.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "cet", "EXALTED", "data")
OUT = os.path.join(ROOT, "internet", "EXALTED", "data")

WRAP = 88          # max chars per generated display line (bumped ~+16% so the
                       # reader fills more of the right side)
VERSE_SEP = "{|}"  # verse separator inside a chapter literal
LINE_SEP = "{~}"   # line separator inside a verse
RED_OPEN = "{r}"
RED_CLOSE = "{/r}"

# KJV margin/cross-reference apparatus, e.g. "+ 8.6 drawn: Heb. pulled" or
# "+ 1.20 Mara: that is, Bitter", is baked into the source text as one or more
# trailing runs. It is translator's apparatus, NOT scripture — drop every run
# so the in-game reader never renders it as body text.
MARGIN_RUN = re.compile(r"\+ \d+\.\d+ ")

# USFM section marker. The Crosswire source prefixes a verse with "¶ " to mark
# a poetic/section break; it is an encoding artifact, not scripture, and it used
# to render as a stray pilcrow at the top of the line in-game (2970 verses
# across 42 of the 66 books). Only ever leading — verified on the whole corpus.
PILCROW = re.compile(r"^(?:\s*¶\s*)+")


def strip_margins(text):
    """Remove trailing KJV margin-note runs (keeps everything before the first
    "+ <chap>.<verse> " marker) plus the two leftovers of that apparatus: a
    leading pilcrow and the dangling colon the note used to sit behind. Source
    data files are never modified."""
    out = PILCROW.sub("", text)
    m = MARGIN_RUN.search(out)
    if not m:
        return out
    body = out[: m.start()]
    # The colon only dangles because the note it introduced was just removed;
    # verses that end in a colon on their own keep it.
    return re.sub(r"\s*:\s*$", "", body)


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def check_bad(text):
    # "¶" is asserted too: strip_margins owns it, so any survivor is a bug and
    # must fail generation rather than ship as a stray glyph.
    for tok in ("{", "}", "~", "¶"):
        if tok in text:
            raise SystemExit(f"source text contains forbidden token {tok!r}: {text[:120]!r}")


def verse_lines(verse, wrap):
    """Build hard-wrapped, single-color lines for one verse.

    verse: dict from kjv json with "v", "text", optional "segs".
    Returns (verse_number, lines) where each line is (red, [words]).
    Runs (plain / Words-of-Jesus) are never merged onto the same line, so a
    generated line is either fully plain or fully wrapped in {r}..{/r}.
    """
    num = int(verse["v"])
    segs = verse.get("segs")
    if segs:
        words = []
        for s in segs:
            red = bool(s.get("r"))
            st = strip_margins(s["t"])
            check_bad(st)
            for w in st.split():
                words.append((red, w))
    else:
        st = strip_margins(verse["text"])
        check_bad(st)
        words = [(False, w) for w in st.split()]
    if not words:
        return (num, [])

    runs = []
    for red, w in words:
        if runs and runs[-1][0] == red:
            runs[-1][1].append(w)
        else:
            runs.append((red, [w]))

    lines = []
    for red, rwords in runs:
        cur = []
        cur_len = 0
        for w in rwords:
            wlen = len(w)
            if cur and cur_len + 1 + wlen > wrap:
                lines.append((red, cur))
                cur = [w]
                cur_len = wlen
            else:
                cur.append(w)
                cur_len += wlen + (1 if len(cur) > 1 else 0)
        if cur:
            lines.append((red, cur))
    return (num, lines)


def lines_to_marked(lines):
    """Render (red, words) lines to redscript-safe strings using {r}..{/r}."""
    out = []
    for red, line in lines:
        t = " ".join(line) if line else ""
        if red:
            out.append(RED_OPEN + t + RED_CLOSE)
        else:
            out.append(t)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    if not os.path.isdir(os.path.join(SRC, "kjv")):
        sys.exit(f"missing source data dir: {SRC}")
    if os.path.abspath(OUT) == os.path.abspath(SRC):
        sys.exit("output dir must differ from source dir")

    books = json.load(open(os.path.join(SRC, "books.json"), encoding="utf-8"))
    total_chapters = 0
    total_verses = 0
    total_red = 0

    for b in books:
        n = int(b["n"])
        path = os.path.join(SRC, "kjv", f"{n}.json")
        chapters = json.load(open(path, encoding="utf-8"))
        book_chapters = int(b["chapters"])
        if len(chapters) != book_chapters:
            sys.exit(f"book {n} {b['name']}: {len(chapters)} chapters in data, canon says {book_chapters}")
        # Key order is chapter -> verses; sort by chapter number.
        rows = []
        red_here = 0
        for ch in sorted(chapters, key=int):
            verses = chapters[ch]
            segs_out = []
            for v in verses:
                total_verses += 1
                num, lines = verse_lines(v, WRAP)
                marked = lines_to_marked(lines)
                if any(RED_OPEN in m for m in marked):
                    red_here += 1
                segs_out.append(f'{num}{VERSE_SEP}{LINE_SEP.join(marked)}')
            rows.append((int(ch), VERSE_SEP.join(segs_out)))
            total_chapters += 1
        total_red += red_here

        literals = "\n".join(
            f"    case {ch}: return s\"{esc(text)}\";"
            for ch, text in rows
        )
        mod = f"ExaltedBook{n:02d}"
        src = (
            f"// Generated by scripts/gen-exalted-reds.py — do not edit.\n"
            f"// {b['name']} ({b['short']}), {len(rows)} chapters, {red_here} red-letter verses.\n"
            f"module {mod}\n\n"
            f"public func {mod}Chapter(c: Int32) -> String {{\n"
            f"  switch c {{\n{literals}\n    default: return s\"\";\n  }};\n}}\n"
        )
        with open(os.path.join(OUT, f"{mod}.reds"), "w", encoding="utf-8", newline="\n") as f:
            f.write(src)

    if (len(books), total_chapters, total_verses, total_red) != (66, 1189, 31102, 2028):
        sys.exit(f"count mismatch: {len(books)} books, {total_chapters} chapters, "
                 f"{total_verses} verses, {total_red} red verses")

    name_cases = "\n".join(f"    case {b['n']}: return s\"{esc(b['name'])}\";" for b in books)
    short_cases = "\n".join(f"    case {b['n']}: return s\"{esc(b['short'])}\";" for b in books)
    count_cases = "\n".join(f"    case {b['n']}: return {int(b['chapters'])};" for b in books)
    data_cases = "\n".join(
        f"    case {b['n']}: return ExaltedBook{b['n']:02d}Chapter(chapter);" for b in books
    )
    book_imports = "\n".join(
        f"import ExaltedBook{b['n']:02d}.*" for b in books
    )
    master = (
        "// Generated by scripts/gen-exalted-reds.py — do not edit.\n"
        f"// {len(books)} books, {total_chapters} chapters, {total_verses} verses, {total_red} red-letter verses.\n"
        "module ExaltedData\n\n"
        f"{book_imports}\n\n"
        "public func ExaltedBookTotal() -> Int32 { return 66; }\n"
        f"public func ExaltedVerseTotal() -> Int32 {{ return {total_verses}; }}\n"
        f"public func ExaltedRedTotal() -> Int32 {{ return {total_red}; }}\n\n"
        "public func ExaltedChapterText(book: Int32, chapter: Int32) -> String {\n"
        f"  switch book {{\n{data_cases}\n    default: return s\"\";\n  }};\n}}\n\n"
        "public func ExaltedBookName(book: Int32) -> String {\n"
        f"  switch book {{\n{name_cases}\n    default: return s\"\";\n  }};\n}}\n\n"
        "public func ExaltedBookShort(book: Int32) -> String {\n"
        f"  switch book {{\n{short_cases}\n    default: return s\"\";\n  }};\n}}\n\n"
        "public func ExaltedBookChapterCount(book: Int32) -> Int32 {\n"
        f"  switch book {{\n{count_cases}\n    default: return 0;\n  }};\n}}\n"
    )
    with open(os.path.join(OUT, "ExaltedData.reds"), "w", encoding="utf-8", newline="\n") as f:
        f.write(master)

    print(f"generated {os.path.relpath(OUT)}: {len(books)} books, {total_chapters} chapters, "
          f"{total_verses} verses, {total_red} red-letter verses")


if __name__ == "__main__":
    main()