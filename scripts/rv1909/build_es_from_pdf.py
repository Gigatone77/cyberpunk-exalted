"""Build the Spanish EXALTED text from the printed RV1909 PDF, with a ledger.

Outputs
  <OUT>/<n>.json           canonical verse JSON (same schema as the digital
                           module, filled from the PDF)
  /tmp/opencode/es-diff-ledger.tsv  every verse where the PDF and the digital
                           module disagree, classified

The digital witness is rebuilt from eBible's USFX by
scripts/rv1909/reconstruct_digital_es.py — it is NEVER the shipped output.

Documented structural adjudications
-----------------------------------
2 Crónicas 16 -> 14 verses. The PDF splits this chapter into 15, breaking
    after the semicolon in "…en la ciudad de David; Y pusiéronlo en una
    litera…". Cross-referenced against every English tradition (KJV, Geneva,
    ASV, WEB, BSB, NLT) plus an independent Spanish RV1909 text
    (chasten.ai, OpenBible-derived, public domain): all of them read 14
    verses, keeping the semicolon clause INSIDE v14. The printed split is a
    printing artifact, not a versification difference, so the PDF's v15 is
    merged back into v14. User decision, Oct 4.

1 Crónicas 21 -> 30 verses. The PDF ends the chapter with an extra 31st
    verse. Cross-referenced against Wikisource's Reina-Valera 1909
    (es.wikisource.org/wiki/Biblia_Reina-Valera_1909/1_Cr%C3%B3nicas/21) plus
    RVC and an independent Spanish site: the chapter ends at v30, "Mas David
    no pudo ir allá á consultar á Dios, porque estaba espantado á causa de la
    espada del ángel de Jehová" — which is exactly the PDF's v30. So v30 is
    genuine 1 Crónicas text (NOT 2 Samuel 24:19 bleed) and only v31 is
    spurious. Both digital sources independently agree on 30.

Wording is NOT repaired. The PDF is the chosen authority; its character-level
OCR defects are shipped as-is and recorded in scripts/rv1909/es-variants.tsv
for a later review pass (user decision, Oct 4). The digital text is not a safe
automatic correction witness — in many disagreements the PDF is the correct
one (Éxodo 20:21 "obscuridad" vs digital "osbcuridad").
"""
import json
import re
import sys
import unicodedata
import difflib
import collections
import csv

sys.path.insert(0, "/tmp/opencode")
import rv1909_from_pdf as R

OUT = "/tmp/opencode/es-pdf"
DIG = "/tmp/opencode/es-digital-orig"
LEDGER = "/tmp/opencode/es-diff-ledger.tsv"

# book -> chapter -> (expected_verse_count, note)
OVERRIDES = {
    (14, 16): (14, "PDF v15 merged back into v14 (semicolon clause); all English "
                  "traditions + independent RV1909 read 14"),
    (13, 21): (30, "PDF v31 rejected: bled from 2 Samuel 24:19"),
}

# book -> chapter -> [(target, *sources)] verses folded into `target`
MERGES = {
    (14, 16): [(14, 15)],
}

WORD = re.compile(r"[a-z0-9]+")


def words(s):
    s = unicodedata.normalize("NFKD", s)
    return WORD.findall("".join(c for c in s if not unicodedata.combining(c)).lower())


def main():
    texts = {int(k): v for k, v in json.load(open(R.CACHE)).items()}
    canon = json.load(open(f"{DIG}/books.json", encoding="utf-8"))
    stats = collections.Counter()
    rows = []
    total = 0

    for b in canon:
        n = b["n"]
        kind = "salmo" if b["name"].lower().startswith("salmo") else "cap"
        dig = json.load(open(f"{DIG}/{n}.json", encoding="utf-8"))
        out = {}
        for ch in range(1, b["chapters"] + 1):
            seg = R.chapter_span(texts[n], ch, kind)
            if seg is None:
                raise SystemExit(f"FATAL: {b['name']} {ch}: chapter header not found")
            got = R.verses_of(seg)
            exp, note = OVERRIDES.get((n, ch), (len(dig.get(str(ch), [])), ""))
            if len(got) < exp:
                raise SystemExit(
                    f"FATAL: {b['name']} {ch}: PDF has {len(got)} verses, need {exp}")
            if len(got) > exp:
                stats["override_truncated"] += len(got) - exp
            # fold merged-away PDF verses back into their target verse
            for target, *sources in MERGES.get((n, ch), []):
                joined = got[target].rstrip()
                for s in sources:
                    src = got[s]
                    # drop a trailing PDF line-wrap marker before joining
                    src = re.sub(r"{~}\s*$", "", src).strip()
                    if joined and not joined.endswith((";", ",", ":", "-")):
                        joined += ";"
                    joined = (joined + " " + src).strip()
                    stats["verses_merged"] += 1
                got[target] = joined
            verses = []
            for k in range(1, exp + 1):
                text = got.get(k, "")
                if not text.strip():
                    raise SystemExit(f"FATAL: {b['name']} {ch}:{k} empty verse")
                if "\\" in text or "¶" in text:
                    raise SystemExit(f"FATAL: {b['name']} {ch}:{k} artifact in text")
                verses.append({"v": k, "text": text})
                total += 1
            out[str(ch)] = verses

            # ---- ledger: compare against the digital module ----
            dmap = {e["v"]: e["text"] for e in dig.get(str(ch), [])}
            pdfmap = {v["v"]: v["text"] for v in verses}
            for k in range(1, exp + 1):
                p, d = pdfmap[k], dmap.get(k, "")
                pw, dw = words(p), words(d)
                if pw == dw:
                    stats["identical"] += 1
                    continue
                if "".join(pw) == "".join(dw):
                    cls = "punctuation-only"
                elif difflib.SequenceMatcher(None, "".join(pw), "".join(dw)).ratio() >= 0.90:
                    cls = "orthographic"
                else:
                    # does the digital verse text actually belong to another verse?
                    owner = [q for q in sorted(dmap)
                             if q != k and dw and
                             ("".join(dmap[q]) == "".join(pw) or
                              "".join(words(dmap[q])) in "".join(pw))]
                    cls = f"DIGITAL-MISALIGNED->{owner[0]}" if owner else "SUBSTANTIVE"
                stats[cls.split("->")[0]] += 1
                rows.append((b["name"], ch, k, cls, p.replace("\t", " "),
                             d.replace("\t", " "), note))

        with open(f"{OUT}/{n}.json", "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)

    with open(LEDGER, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["book", "chapter", "verse", "class", "pdf_text", "digital_text", "note"])
        w.writerows(rows)

    print(f"verses written        : {total}")
    print(f"ledger rows           : {len(rows)}")
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {k:26} {v}")


if __name__ == "__main__":
    main()