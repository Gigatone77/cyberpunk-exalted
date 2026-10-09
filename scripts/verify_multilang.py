#!/usr/bin/env python3
"""Validate a multi-language EXALTED site tree produced by scripts/langify.py.

The single-language build validates one ``ExaltedData.reds`` inside
package.sh's URL-slug gate. The combined tree ships six suffixed
``ExaltedData<Sfx>.reds`` dispatchers and one ``ExaltedLang.reds``, so this
script applies the SAME guarantees per language and then a few cross-tree ones.

Per language module ``ExaltedData<Sfx>.reds``:
  * ``ExaltedBookName``/``ExaltedBookShort`` cover the same, contiguous 1..N books;
  * every slug is ASCII route-safe and is a canonical KJV short equal to the
    canonical slug for that book number (slugs are shared across languages so
    ``/b/<short>`` resolves in every language);
  * ``ExaltedBookTotal`` matches the number of emitted cases;
  * exactly N ``ExaltedBookNN<Sfx>.reds`` modules exist.

Across the tree:
  * ``ExaltedLang.reds`` exists and ``ExaltedLangTotal`` equals the number of
    language modules;
  * every ``ExaltedData<Sfx>`` is imported by ``ExaltedLang.reds``;
  * no ``case <n>: if `` anywhere (langify once emitted that; it is invalid
    redscript).

Read-only. Never touches Bible source. Exit 0 = pass, 1 = fail.
"""
import glob
import json
import os
import re
import sys

SLUG_RE = re.compile(r"^[A-Za-z0-9]{1,12}$")
CASE_RE = re.compile(r'^\s*case (\d+): return s"(.*)";\s*$')
DATA_RE = re.compile(r"^ExaltedData([A-Z][a-z]+)\.reds$")
BAD_SWITCH_RE = re.compile(r"case \d+:\s*if ")


def cases(text, func):
    m = re.search(
        r"public func " + func + r"\(book: Int32\) -> String \{(.*?)\n\}", text, re.S
    )
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        c = CASE_RE.match(line)
        if c:
            out[int(c.group(1))] = c.group(2)
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: verify_multilang.py <data-dir> <canonical-books.json>")
    data_dir, canon_path = sys.argv[1], sys.argv[2]

    canon = json.load(open(canon_path, encoding="utf-8"))
    canon_short = {int(b["n"]): b["short"] for b in canon}
    canon_all_shorts = {b["short"] for b in canon}

    masters = sorted(
        os.path.basename(p)
        for p in glob.glob(os.path.join(data_dir, "ExaltedData*.reds"))
    )
    if not masters:
        sys.exit(f"ERROR: no ExaltedData*.reds in {data_dir}")
    if not any(m == "ExaltedData.reds" for m in masters) and len(masters) < 2:
        sys.exit("ERROR: single ExaltedData.reds only — that is a one-language tree, "
                 "not a multi-language tree")

    errors = []
    suffixes = []
    lang_path = os.path.join(data_dir, "ExaltedLang.reds")
    if not os.path.isfile(lang_path):
        sys.exit(f"ERROR: {lang_path} missing — run scripts/langify.py first")
    lang_text = open(lang_path, encoding="utf-8").read()

    for name in masters:
        m = DATA_RE.match(name)
        if not m:
            errors.append(f"{name}: unexpected ExaltedData module name")
            continue
        sfx = m.group(1)
        suffixes.append(sfx)
        text = open(os.path.join(data_dir, name), encoding="utf-8").read()

        names = cases(text, f"ExaltedBookName{sfx}")
        shorts = cases(text, f"ExaltedBookShort{sfx}")
        if shorts is None:
            errors.append(f"[{sfx}] ExaltedBookShort{sfx}() not found")
        if names is None:
            errors.append(f"[{sfx}] ExaltedBookName{sfx}() not found")
        if names is None or shorts is None:
            continue
        if set(names) != set(shorts):
            errors.append(f"[{sfx}] Name/Short cover different books")
            continue

        nums = sorted(shorts)
        if nums != list(range(1, len(nums) + 1)):
            errors.append(f"[{sfx}] book numbers not contiguous 1..N")

        tm = re.search(
            rf"public func ExaltedBookTotal{sfx}\(\) -> Int32 \{{ return (\d+); \}}", text)
        if not tm or int(tm.group(1)) != len(nums):
            errors.append(f"[{sfx}] ExaltedBookTotal{sfx}() missing or != {len(nums)} cases")

        mods = glob.glob(os.path.join(data_dir, f"ExaltedBook*{sfx}.reds"))
        if len(mods) != len(nums):
            errors.append(f"[{sfx}] {len(mods)} book modules but {len(nums)} books declared")

        for n in nums:
            s = shorts[n]
            if not s:
                errors.append(f"[{sfx}] book {n}: empty slug")
            elif not SLUG_RE.match(s):
                errors.append(f"[{sfx}] book {n}: slug {s!r} is not route-safe ASCII")
            elif s != canon_short.get(n):
                errors.append(
                    f"[{sfx}] book {n}: slug {s!r} != canonical KJV {canon_short.get(n)!r}")
            elif s not in canon_all_shorts:
                errors.append(f"[{sfx}] book {n}: slug {s!r} not a canonical KJV short")
            if not names[n].strip():
                errors.append(f"[{sfx}] book {n}: empty display name")

        if f"import ExaltedData{sfx}.*" not in lang_text:
            errors.append(f"{name}: not imported by ExaltedLang.reds")

    tm = re.search(r"public func ExaltedLangTotal\(\) -> Int32 \{ return (\d+); \}", lang_text)
    if not tm:
        errors.append("ExaltedLang.reds: ExaltedLangTotal() missing")
    elif int(tm.group(1)) != len(suffixes):
        errors.append(
            f"ExaltedLangTotal()={tm.group(1)} but {len(suffixes)} language modules present")

    for path in glob.glob(os.path.join(data_dir, "*.reds")):
        if BAD_SWITCH_RE.search(open(path, encoding="utf-8").read()):
            errors.append(f"{os.path.basename(path)}: invalid 'case <n>: if '")

    if errors:
        print(f"ERROR: multi-language gate FAILED — {len(errors)} problem(s):", file=sys.stderr)
        for e in errors[:60]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 60:
            print(f"  ... and {len(errors) - 60} more", file=sys.stderr)
        sys.exit(1)

    print(f"  multi-language gate ok: {len(suffixes)} languages "
          f"({', '.join(suffixes)}), {len(canon_all_shorts)} canonical slugs, "
          f"no invalid switches")


if __name__ == "__main__":
    main()
