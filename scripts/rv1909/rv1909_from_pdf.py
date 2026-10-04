"""Extract the complete Reina-Valera 1909 text from the local printed PDF set.

This is the AUTHORITATIVE source for the Spanish EXALTED pack. The eBible /
wordproject / BibleAquifer digital modules are NOT usable as a base: measured
against the printed text they contain 18 empty verses and ~146 silently
misaligned verses (e.g. Job 40 is shifted +5 verses, digital v10 holds v15).

Structural contract: every chapter must yield exactly the canon verse count.
Anything else is a hard failure, never a silent partial.
"""
import json
import re
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor

PDF_DIR = "/tmp/opencode/sp-pdf/Spanish"
CACHE = "/tmp/opencode/pdftext.json"

JUNK = re.compile(
    r"(For other languages please go to|www\.wordproject\.org|"
    r"Reina-Valera|Copyright|\bISBN\b|\bpágina\b)", re.I)
WORD = re.compile(r"[a-z0-9]+")
NUM_LINE = (r"(?m)^[ \t]{0,8}(\d{1,3})[ \t]*$",
            r"(?m)^[ \t]{0,8}(\d{1,3})[ \t]{1,4}(?=\S)",
            # -layout merges a marginal verse number onto the end of the
            # preceding line. A wide gap distinguishes it from real text.
            r"(?m)[ \t]{4,}(\d{1,3})[ \t]*$")


def words(s):
    s = unicodedata.normalize("NFKD", s)
    return WORD.findall("".join(c for c in s if not unicodedata.combining(c)).lower())


def norm(s):
    return "".join(words(s))


def load_texts():
    def one(n):
        out = subprocess.run(["pdftotext", "-layout", f"{PDF_DIR}/{n}.pdf", "-"],
                             capture_output=True, text=True).stdout
        return "\n".join(JUNK.sub("", line) for line in out.splitlines())
    with ThreadPoolExecutor(8) as ex:
        return dict(zip(range(1, 67), ex.map(one, range(1, 67)), strict=True))


def chapter_span(t, ch, kind):
    word = r"SALMO" if kind == "salmo" else r"CAP[ÍI]TULO"
    m = re.search(rf"{word} {ch}\b", t)
    if not m:
        return None
    nxt = re.search(rf"{word} \d+\b", t[m.end():])
    return t[m.end(): m.end() + nxt.start()] if nxt else t[m.end():]


def verses_of(seg):
    """Split a chapter segment into {verse: text}.

    Verse 1 carries no number in this printing, so everything before the first
    '2' marker belongs to verse 1 (this is also where a Psalm superscription
    lives - correct for RV1909, where the superscription is part of verse 1).
    """
    cand = {}
    for rx in NUM_LINE:
        for mm in re.finditer(rx, seg):
            cand.setdefault(int(mm.group(1)), mm.start(1))
    seq, v = [], 2
    while v in cand:
        seq.append(v)
        v += 1
    clean = lambda x: re.sub(r"\s+", " ", x).strip()
    out = {}
    if seq and seq[0] == 2:
        out[1] = clean(seg[:cand[2]])
    for i, num in enumerate(seq):
        end = cand[seq[i + 1]] if i + 1 < len(seq) else len(seg)
        out[num] = clean(seg[cand[num] + len(str(num)):end])
    return out


def psalm_superscription_leak(t, ch):
    """True if a SALMO chapter header appears AFTER its superscription."""
    m = re.search(rf"SALMO {ch}\b", t)
    if not m:
        return False
    head = t[:m.start()]
    last_sup = list(re.finditer(r"SALMO DE\b", head))
    if not last_sup:
        return False
    tail = head[last_sup[-1].start():]
    return not re.search(r"SALMO \d+\b", tail)


def main():
    texts = json.load(open(CACHE))
    texts = {int(k): v for k, v in texts.items()}
    canon = json.load(open("/var/home/Gigatone/cyberpunk-exalted/translations/es/books.json",
                           encoding="utf-8"))
    digital_dir = "/var/home/Gigatone/cyberpunk-exalted/translations/es"

    problems, total, ok = [], 0, 0
    for b in canon:
        n, kind = b["n"], ("salmo" if b["name"].lower().startswith("salmo") else "cap")
        dig = json.load(open(f"{digital_dir}/{n}.json", encoding="utf-8"))
        for ch in range(1, b["chapters"] + 1):
            exp = len(dig.get(str(ch), []))
            seg = chapter_span(texts[n], ch, kind)
            if seg is None:
                problems.append((n, ch, exp, 0, "chapter not found"))
                continue
            got = verses_of(seg)
            blanks = [k for k, t in got.items() if not t.strip()]
            if len(got) != exp or blanks or max(got, default=0) != exp:
                problems.append((n, ch, exp, len(got),
                                 f"blanks={blanks[:5]} maxv={max(got, default=0)}"))
            else:
                ok += 1
            total += 1
    print(f"chapters checked : {total}")
    print(f"structurally OK : {ok}")
    print(f"problems        : {len(problems)}")
    for p in problems[:40]:
        print("   book", p[0], "ch", p[1], "expected", p[2], "got", p[3], p[4])
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())