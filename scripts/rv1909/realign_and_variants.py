"""Realign the digital RV1909 module onto the printed PDF's verse numbering, then
list every genuine word-level variant between them.

The digital module is misaligned in 150+ verses (chapter-boundary bleeds and
in-chapter shifts), so a naive same-number comparison is useless. SequenceMatcher
over the normalised verse sequences recovers the true correspondence, and what
remains after realignment is a real textual variant rather than a shift.

Output: /tmp/opencode/es-variants.tsv
"""
import difflib
import json
import re
import unicodedata
import collections
import csv

WORD = re.compile(r"[a-z0-9]+")
PDF_DIR = "/tmp/opencode/es-pdf"
DIG = "/tmp/opencode/es-digital-orig"
OUT = "/tmp/opencode/es-variants.tsv"
GUT = "/tmp/opencode/gut_nt.txt"


def words(s):
    s = unicodedata.normalize("NFKD", s)
    return WORD.findall("".join(c for c in s if not unicodedata.combining(c)).lower())


def main():
    canon = json.load(open(f"{DIG}/books.json", encoding="utf-8"))
    gut = words(open(GUT, encoding="utf-8", errors="replace").read())
    gset = collections.Counter(gut)

    rows, stats = [], collections.Counter()

    for b in canon:
        n = b["name"]
        pdf = json.load(open(f"{PDF_DIR}/{b['n']}.json", encoding="utf-8"))
        dig = json.load(open(f"{DIG}/{b['n']}.json", encoding="utf-8"))
        for ch in pdf:
            pv = [(v["v"], v["text"]) for v in pdf[ch]]
            dv = [(e["v"], e["text"]) for e in dig.get(ch, [])]
            pk = ["".join(words(t)) for _, t in pv]
            dk = ["".join(words(t)) for _, t in dv]
            sm = difflib.SequenceMatcher(None, pk, dk, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    stats["aligned identical"] += (i2 - i1)
                    continue
                # pair the differing blocks positionally where possible
                npair = min(i2 - i1, j2 - j1)
                for off in range(npair):
                    a, bkt = pv[i1 + off], dv[j1 + off]
                    stats["aligned differing"] += 1
                    aw, bw = words(a[1]), words(bkt[1])
                    if aw == bw:
                        continue
                    ca = difflib.SequenceMatcher(None, aw, bw, autojunk=False)
                    for t2, x1, x2, y1, y2 in ca.get_opcodes():
                        if t2 == "equal":
                            continue
                        only_pdf = aw[x1:x2]
                        only_dig = bw[y1:y2]
                        # a real variant is a substitution of actual words
                        if not only_pdf and not only_dig:
                            continue
                        cls = "reorder/insert/delete"
                        if only_pdf and only_dig:
                            near = difflib.SequenceMatcher(
                                None, "".join(only_pdf), "".join(only_dig)).ratio()
                            cls = ("near-miss (typo)" if near >= 0.80
                                   else "wording variant")
                            # Gutenberg can arbitrate the NT
                            if b["n"] >= 40:
                                pin = all(gset[w] > 0 for w in only_pdf)
                                din = all(gset[w] > 0 for w in only_dig)
                                if pin and not din:
                                    cls += " | Gutenberg:PDF"
                                elif din and not pin:
                                    cls += " | Gutenberg:DIGITAL"
                        stats[cls] += 1
                        rows.append((n, ch, a[0], bkt[0], cls,
                                     " ".join(only_pdf), " ".join(only_dig)))
                # unpaired leftovers = verses the digital lost or invented
                for off in range(npair, i2 - i1):
                    stats["PDF verse with no digital counterpart"] += 1
                    rows.append((n, ch, pv[i1 + off][0], "", "PDF-ONLY", "", ""))
                for off in range(npair, j2 - j1):
                    stats["digital verse with no PDF counterpart"] += 1
                    rows.append((n, ch, "", dv[j1 + off][0], "DIGITAL-ONLY", "", ""))

    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["book", "chapter", "pdf_verse", "digital_verse", "class",
                    "pdf_words", "digital_words"])
        w.writerows(rows)

    print("realignment + variant scan")
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {k:44} {v}")
    print(f"\nrows written: {len(rows)}  -> {OUT}")


if __name__ == "__main__":
    main()