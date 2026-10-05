"""Reconstruct the ORIGINAL digital Spanish module from eBible's single USFX file.

Why this exists
---------------
translations/es is the BUILD OUTPUT (PDF-derived). The eBible/wordproject/
BibleAquifer digital text is only a COMPARISON WITNESS — it has broken verse
numbering (silent chapter shifts, 18 empty targets, 2 Crónicas 16 merged), so it
must never ship, but the audit ledger needs it. This rebuilds it from
spaRV1909_usfx.xml so the ledger is reproducible from source instead of relying
on a file we overwrote.

Output: a scratch directory of canonical verse JSON, NOT translations/es.
"""
import hashlib
import html
import json
import pathlib
import re
import sys

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                    else "/tmp/opencode/usfx_x/spaRV1909_usfx.xml")
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2
                   else "/tmp/opencode/es-digital-orig")
BOOKS = pathlib.Path("/var/home/Gigatone/cyberpunk-exalted/translations/es/books.json")

BOOK_RE = re.compile(r'<book id="([A-Z0-9]+)">(.*?)</book>', re.S)
H_RE = re.compile(r"<h>(.*?)</h>", re.S)
C_RE = re.compile(r'<c id="(\d+)"\s*/>')
V_RE = re.compile(r'<v id="(\d+)"\s*/>')
VE_RE = re.compile(r"<ve\s*/>")
TAG_RE = re.compile(r"<[^>]+>")
# USFM paragraph/division markers carry no verse text
DROP_RE = re.compile(r"<p\b[^>]*>|</p>|<mt\b[^>]*>.*?</mt>|<qt\b[^>]*>.*?</qt>|"
                     r"<s1\b[^>]*>.*?</s1>|<s2\b[^>]*>.*?</s2>|"
                     r"<rem\b[^>]*>.*?</rem>|<figure\b[^>]*>.*?</figure>", re.S)
WS_RE = re.compile(r"\s+")


def verse_text(raw):
    raw = DROP_RE.sub(" ", raw)
    raw = TAG_RE.sub("", raw)
    raw = html.unescape(raw)
    return WS_RE.sub(" ", raw).strip()


def main():
    data = SRC.read_text(encoding="utf-8", errors="replace")
    canon = json.loads(BOOKS.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    books = BOOK_RE.findall(data)
    if len(books) != 66:
        raise SystemExit(f"expected 66 <book> elements, found {len(books)}")

    made = {}
    for idx, (_usfm_id, body) in enumerate(books, start=1):
        b = canon[idx - 1]
        out = {}
        chapters = [(int(m.group(1)), m.end()) for m in C_RE.finditer(body)]
        for ci, (cnum, cstart) in enumerate(chapters):
            cend = chapters[ci + 1][1] if ci + 1 < len(chapters) else len(body)
            seg = body[cstart:cend]
            verses = [(int(m.group(1)), m.end()) for m in V_RE.finditer(seg)]
            chap = []
            for vi, (vnum, vstart) in enumerate(verses):
                vend = verses[vi + 1][1] if vi + 1 < len(verses) else len(seg)
                chunk = seg[vstart:vend]
                end = VE_RE.search(chunk)
                if end:
                    chunk = chunk[:end.start()]
                text = verse_text(chunk)
                chap.append({"v": vnum, "text": text})
            out[str(cnum)] = chap
        path = OUT / f"{b['n']}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        made[b["name"]] = (b["n"], len(out), sum(len(v) for v in out.values()))

    tot = sum(v[2] for v in made.values())
    empt = 0
    for b in canon:
        d = json.loads((OUT / f"{b['n']}.json").read_text(encoding="utf-8"))
        empt += sum(1 for ch in d.values() for v in ch if not v["text"].strip())

    digest = hashlib.sha256()
    for b in canon:
        digest.update((OUT / f"{b['n']}.json").read_bytes())

    print(f"books      : {len(canon)}")
    print(f"chapters   : {sum(len(json.loads((OUT / f'{b['n']}.json').read_text(encoding='utf-8'))) for b in canon)}")
    print(f"verses     : {tot}")
    print(f"empty      : {empt}   (the 18 known digital gaps; 2 Crónicas 16 is not")
    print( "              one of them - it is MERGED, so the 19th gap appears only")
    print( "              when the text is aligned to the PDF's 15-verse split)")
    print(f"sha256     : {digest.hexdigest()}")
    for name in ("Job", "2 Crónicas", "Números", "1 Samuel"):
        print(f"  {name:12} {made[name]}")


if __name__ == "__main__":
    main()