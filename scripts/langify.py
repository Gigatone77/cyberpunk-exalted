#!/usr/bin/env python3
"""Build EXALTED multi-language redscript modules.

Takes ALREADY-VERIFIED per-language ``data/`` trees (the exact .reds files that
ship in each per-language pack) and emits a single combined tree in which every
module and every public symbol carries a per-language suffix.

Why suffix instead of nesting in directories: REDscript module names are the
flat file basenames across all of r6/scripts and r6/tweaks. A German
``ExaltedBook01.reds`` and a Czech ``ExaltedBook01.reds`` are the SAME module
name and the second one silently wins. Suffixing (``ExaltedBook01Deu`` /
``ExaltedBook01Cze``) is the only reliable namespacing.

Only module/function NAMES are rewritten. The s"..." text literals are copied
byte-for-byte, so every Bible verification result (66 books / chapter and verse
counts / 0 artifacts / canon purity) carries over unchanged -- this script does
not re-parse scripture and cannot alter a verse.

Emits, into ``--out``:
  ExaltedBookNN<Sfx>.reds   per-book chapter text, suffixed
  ExaltedData<Sfx>.reds      per-language dispatcher, suffixed + chapter total
  ExaltedUi<Sfx>.reds        per-language UI string table
  ExaltedLang.reds           combined language list + cross-language dispatcher
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOOK_RE = re.compile(r"ExaltedBook(\d\d)")
LIT_RE = re.compile(r's"((?:[^"\\]|\\.)*)"')


def literals(text):
    """Every s"..." literal in a redscript file, in order."""
    return LIT_RE.findall(text)

# Public symbols ExaltedData exposes. Every one is suffixed so that importing
# several ExaltedData<Sfx> modules into ExaltedLang cannot collide.
DATA_SYMBOLS = [
    "ExaltedBookTotal",
    "ExaltedVerseTotal",
    "ExaltedRedTotal",
    "ExaltedChapterText",
    "ExaltedBookName",
    "ExaltedBookShort",
    "ExaltedBookChapterCount",
]


def esc(s):
    """Escape a string for a redscript s"..." literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def suffix_book_mods(text, sfx):
    """Rename ExaltedBookNN -> ExaltedBookNN<Sfx> (module, import, call sites)."""
    return BOOK_RE.sub(lambda m: f"ExaltedBook{m.group(1)}{sfx}", text)


def suffix_data_mods(text, sfx):
    """Rename ExaltedData and the public dispatch symbols."""
    text = re.sub(r"\bExaltedData\b", f"ExaltedData{sfx}", text)
    for sym in DATA_SYMBOLS:
        text = re.sub(rf"\b{sym}\b", f"{sym}{sfx}", text)
    return text


def chapter_total(data_text):
    """Sum the per-book chapter counts actually emitted in an ExaltedData tree."""
    block = data_text.split("func ExaltedBookChapterCount")[1]
    total = 0
    for m in re.finditer(r"case \d+: return (\d+);", block):
        total += int(m.group(1))
    return total


def verse_total(data_text):
    m = re.search(r"ExaltedVerseTotal\(\) -> Int32 \{ return (\d+);", data_text)
    return int(m.group(1)) if m else 0


def red_total(data_text):
    m = re.search(r"ExaltedRedTotal\(\) -> Int32 \{ return (\d+);", data_text)
    return int(m.group(1)) if m else 0


def book_total(data_text):
    m = re.search(r"ExaltedBookTotal\(\) -> Int32 \{ return (\d+);", data_text)
    return int(m.group(1)) if m else 0


def build_language(lang, srcdir, outdir, keys):
    """Suffix one language's tree and write its modules. Returns a stat dict."""
    sfx = lang["suffix"]
    data = os.path.join(srcdir, "data")
    if not os.path.isdir(data):
        sys.exit(f"[{lang['code']}] no data/ under {srcdir}")

    books = sorted(f for f in os.listdir(data)
                   if re.fullmatch(r"ExaltedBook\d\d\.reds", f))
    n_books = len(books)
    master_path = os.path.join(data, "ExaltedData.reds")
    if not os.path.isfile(master_path):
        sys.exit(f"[{lang['code']}] missing ExaltedData.reds")

    master = open(master_path, encoding="utf-8").read()

    src_lits = literals(master)
    for name in books:
        text = open(os.path.join(data, name), encoding="utf-8").read()
        src_book_lits = literals(text)
        text = suffix_book_mods(text, sfx)
        out_name = BOOK_RE.sub(lambda m: f"ExaltedBook{m.group(1)}{sfx}", name)
        with open(os.path.join(outdir, out_name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        # The whole safety argument for suffixing is that this cannot alter text.
        if literals(text) != src_book_lits:
            sys.exit(f"[{lang['code']}] {name}: literals changed during suffixing")

    # Per-language dispatcher, with a chapter total the original did not expose
    # (the multi-language stats line needs chapters for the *selected* language).
    # Read every total from the ORIGINAL text: suffix_data_mods renames the very
    # functions these regexes match, so they must be captured first.
    chap_total = chapter_total(master)
    stats = {
        "books": book_total(master),
        "chapters": chap_total,
        "verses": verse_total(master),
        "red": red_total(master),
    }
    extra = (f"\npublic func ExaltedChapterTotal{sfx}() -> Int32 "
             f"{{ return {chap_total}; }}\n")
    master = suffix_data_mods(master, sfx)
    # keep the generated-by banner truthful
    master = master.replace(
        "// Generated by scripts/gen-exalted-reds.py \u2014 do not edit.",
        "// Generated by scripts/langify.py (names only) from the verified "
        f"{lang['code']} tree \u2014 do not edit.")
    master = master.replace(
        f"module ExaltedData{sfx}\n",
        f"module ExaltedData{sfx}\n", 1)
    with open(os.path.join(outdir, f"ExaltedData{sfx}.reds"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(master.rstrip("\n") + "\n" + extra)

    out_master = master.rstrip("\n") + "\n" + extra
    if literals(out_master) != src_lits:
        sys.exit(f"[{lang['code']}] ExaltedData literals changed during suffixing")

    # UI string table
    cases = []
    for i, key in enumerate(keys):
        val = lang[key]
        cases.append(f'    case {i}: return s"{esc(val)}";')
    ui = (
        "// Generated by scripts/langify.py from translations/ui.json \u2014 do not edit.\n"
        f"// {lang['name_en']} ({lang['endonym']}) UI strings.\n"
        f"module ExaltedUi{lang['suffix']}\n\n"
        f"public func ExaltedUiKeyTotal{lang['suffix']}() -> Int32 {{ return {len(keys)}; }}\n\n"
        "public func ExaltedUiStr" + lang["suffix"] + "(key: Int32) -> String {\n"
        "  switch key {\n" + "\n".join(cases) + "\n    default: return s\"\";\n  };\n}\n"
    )
    with open(os.path.join(outdir, f"ExaltedUi{lang['suffix']}.reds"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(ui)

    return {
        "code": lang["code"],
        "suffix": sfx,
        "modules": n_books + 2,
        **stats,
    }


def key_index(keys, code, name):
    """Numeric literal for a named UI key, so Site.reds stays readable."""
    if name not in keys:
        sys.exit(f"unknown ui key: {name}")
    return keys.index(name)


def build_lang_module(langs, stats, keys):
    """The combined dispatcher: language list + per-language text dispatch."""
    imports = "\n".join(f"import ExaltedData{s['suffix']}.*\n"
                        f"import ExaltedUi{s['suffix']}.*" for s in stats)

    def switch(expr, cases, default):
        body = "\n".join(f"    case {i}: {c}" for i, c in enumerate(cases))
        return (f"  switch {expr} {{\n{body}\n    default: {default};\n  }};\n")

    code_cases = [f'return s"{esc(l["code"])}";' for l in langs]
    endo_cases = [f'return s"{esc(l["endonym"])}";' for l in langs]
    name_cases = [f'return s"{esc(l["name_en"])}";' for l in langs]
    text_cases = [f"return ExaltedChapterText{s['suffix']}(book, chapter);" for s in stats]
    nm_cases = [f"return ExaltedBookName{s['suffix']}(book);" for s in stats]
    sh_cases = [f"return ExaltedBookShort{s['suffix']}(book);" for s in stats]
    cc_cases = [f"return ExaltedBookChapterCount{s['suffix']}(book);" for s in stats]
    ct_cases = [f"return ExaltedChapterTotal{s['suffix']}();" for s in stats]
    vt_cases = [f"return ExaltedVerseTotal{s['suffix']}();" for s in stats]
    rt_cases = [f"return ExaltedRedTotal{s['suffix']}();" for s in stats]
    ui_cases = [f"return ExaltedUiStr{s['suffix']}(key);" for s in stats]
    book_cases = [f"return ExaltedBookTotal{s['suffix']}();" for s in stats]
    # OfCode is a lookup, not a per-value dispatch, so it must be an if-chain:
    # a switch whose cases contain `if` statements is not valid redscript.
    of_code = "\n".join(
        f'  if Equals(code, s"{esc(l["code"])}") {{ return {i}; }}'
        for i, l in enumerate(langs))

    return (
        "// Generated by scripts/langify.py \u2014 do not edit.\n"
        f"// EXALTED language dispatcher: {len(stats)} language(s), "
        f"{sum(s['chapters'] for s in stats)} chapters, "
        f"{sum(s['verses'] for s in stats)} verses.\n"
        "module ExaltedLang\n\n"
        f"{imports}\n"
        f"public func ExaltedLangTotal() -> Int32 {{ return {len(stats)}; }}\n\n"
        "public func ExaltedLangCode(l: Int32) -> String {\n"
        + switch("l", code_cases, 'return s"";')
        + "}\n\n"
        "public func ExaltedLangEndonym(l: Int32) -> String {\n"
        + switch("l", endo_cases, 'return s"";')
        + "}\n\n"
        "public func ExaltedLangName(l: Int32) -> String {\n"
        + switch("l", name_cases, 'return s"";')
        + "}\n\n"
        "public func ExaltedLangOfCode(code: String) -> Int32 {\n"
        + of_code + "\n  return 0;\n}\n\n"
        "public func ExaltedLangChapterText(l: Int32, book: Int32, chapter: Int32) -> String {\n"
        + switch("l", text_cases, 'return s"";')
        + "}\n\n"
        "public func ExaltedLangBookName(l: Int32, book: Int32) -> String {\n"
        + switch("l", nm_cases, 'return s"";')
        + "}\n\n"
        "public func ExaltedLangBookShort(l: Int32, book: Int32) -> String {\n"
        + switch("l", sh_cases, 'return s"";')
        + "}\n\n"
        "public func ExaltedLangBookChapterCount(l: Int32, book: Int32) -> Int32 {\n"
        + switch("l", cc_cases, "return 0;")
        + "}\n\n"
        "public func ExaltedLangChapterTotal(l: Int32) -> Int32 {\n"
        + switch("l", ct_cases, "return 0;")
        + "}\n\n"
        "public func ExaltedLangVerseTotal(l: Int32) -> Int32 {\n"
        + switch("l", vt_cases, "return 0;")
        + "}\n\n"
        "public func ExaltedLangRedTotal(l: Int32) -> Int32 {\n"
        + switch("l", rt_cases, "return 0;")
        + "}\n\n"
        "public func ExaltedLangBookTotal(l: Int32) -> Int32 {\n"
        + switch("l", book_cases, "return 0;")
        + "}\n\n"
        "public func ExaltedUiLangStr(l: Int32, key: Int32) -> String {\n"
        + switch("l", ui_cases, 'return s"";')
        + "}\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", required=True,
                    help="dir holding <lang>/data trees (lang = code from ui.json)")
    ap.add_argument("--ui", default=os.path.join(ROOT, "translations", "ui.json"))
    ap.add_argument("--out", required=True, help="output dir for combined .reds")
    ap.add_argument("--only", default="",
                    help="comma-separated subset of language codes to include")
    args = ap.parse_args()

    cfg = json.load(open(args.ui, encoding="utf-8"))
    keys = cfg["keys"]
    langs = [cfg["languages"][c] for c in cfg["order"]]
    if args.only:
        want = {c.strip() for c in args.only.split(",") if c.strip()}
        unknown = want - {l["code"] for l in langs}
        if unknown:
            sys.exit(f"unknown language code(s): {sorted(unknown)}")
        langs = [l for l in langs if l["code"] in want]

    # Every key must be present in every language, else the UI silently renders
    # an empty string. Empty string is LEGAL (Spanish has no red letters).
    for l in langs:
        missing = [k for k in keys if k not in l]
        if missing:
            sys.exit(f"[{l['code']}] ui.json missing key(s): {missing}")

    os.makedirs(args.out, exist_ok=True)
    stats = [build_language(l, os.path.join(args.stage, l["code"]),
                            args.out, keys) for l in langs]

    with open(os.path.join(args.out, "ExaltedLang.reds"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(build_lang_module(langs, stats, keys))

    # Key index map for Site.reds, so it can write EXAL_S(12) and stay readable.
    idx = {k: key_index(keys, l["code"], k) for k in keys for l in langs[:1]}
    with open(os.path.join(args.out, "ExaltedUiKeys.txt"), "w",
              encoding="utf-8", newline="\n") as f:
        for k in keys:
            f.write(f"{k}={idx[k]}\n")

    print(f"multi-language tree -> {args.out}")
    for s in stats:
        print(f"  {s['code']:<4} {s['modules']:>3} modules  "
              f"{s['books']} books  {s['chapters']} chapters  "
              f"{s['verses']} verses  {s['red']} red")
    print(f"  total literals ~{sum(s['chapters'] + s['red'] * 0 + 0 for s in stats)} "
          f"chapters across {len(stats)} languages")
    print("UI keys: " + ", ".join(f"{k}={idx[k]}" for k in keys))


if __name__ == "__main__":
    main()