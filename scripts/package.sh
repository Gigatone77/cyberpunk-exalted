#!/usr/bin/env bash
# Package the mod as Nexus-style zips: game-relative trees at the zip root
# so extracting into the game root installs them — like standard CP2077
# Nexus mods. Pure Lua + pure redscript: data ships inside, no host binary.
#
# Produces three zips:
#   EXALTED_Terminal_77-0.1.5.zip        — UNIFIED (CET + browser site)
#   EXALTED_Terminal_77-CET-0.1.5.zip    — CET surface only
#   EXALTED_Terminal_77-Browser-0.1.2.zip — in-game browser site only
#
# Version overrides via env: EXALTED_VERSION (CET, default from init.lua),
# EXALTED_BROWSER_VERSION (browser site, default 0.1.2).
#
# Per-language overrides (added for the Spanish RV1909 pilot) so a language can
# be packaged WITHOUT touching the shipped English tree:
#   EXALTED_SITE_SRC — browser site source tree (default internet/EXALTED)
#   EXALTED_LANG_TAG — language slug appended to the browser zip name
#                      (e.g. "es" -> EXALTED_Terminal_77-Browser-es-0.1.2.zip)
#   EXALTED_SKIP_CET — set to 1 to build only the browser zip (the CET surface
#                      reads cet/EXALTED/data/ and is English-only, so a
#                      language build MUST set this)
#   EXALTED_DIST     — output dir (default <repo>/dist). Point this at a
#                      scratch dir to verify a language build without
#                      publishing into dist/.
# The staging dir is always a fresh mktemp -d that this script deletes on exit.
# It is deliberately NOT overridable: it is rm -rf'd by the EXIT trap, so an
# override would let a caller aim that rm at an existing directory. Set TMPDIR
# instead if the stage needs to live on a particular volume.
#
# NOTE: the CET surface reads cet/EXALTED/data/ directly and is still
# English-only; a translated CET surface needs its own cache.lua build.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DIST="${EXALTED_DIST:-$REPO/dist}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# Read the CET version from init.lua, but only if that file is actually here.
# A tools-only mirror (e.g. the ToolBox drive copy) carries scripts/ + the
# canonical books.json but not the product tree, and an unguarded sed on a
# missing file kills the whole script under `set -e`.
if [ -z "${EXALTED_VERSION:-}" ] && [ -f "$REPO/cet/EXALTED/init.lua" ]; then
    EXALTED_VERSION="$(sed -n 's/^[[:space:]]*version[[:space:]]*=[[:space:]]*"\([0-9.]*\)".*/\1/p' "$REPO/cet/EXALTED/init.lua" | head -n1)"
fi
CET_VERSION="${EXALTED_VERSION:-0.1.5}"
BROWSER_VERSION="${EXALTED_BROWSER_VERSION:-0.1.2}"
SITE_SRC="${EXALTED_SITE_SRC:-$REPO/internet/EXALTED}"
LANG_TAG="${EXALTED_LANG_TAG:-}"
SKIP_CET="${EXALTED_SKIP_CET:-0}"
CANON_BOOKS="$REPO/cet/EXALTED/data/books.json"

LANG_PART=""
[ -n "$LANG_TAG" ] && LANG_PART="-$LANG_TAG"

CET_ZIP="EXALTED_Terminal_77-${CET_VERSION}.zip"
CET_ONLY_ZIP="EXALTED_Terminal_77-CET-${CET_VERSION}.zip"
BROWSER_ZIP="EXALTED_Terminal_77-Browser${LANG_PART}-${BROWSER_VERSION}.zip"

if [ ! -f "$CANON_BOOKS" ]; then
    echo "ERROR: canonical cet/EXALTED/data/books.json missing — run the bibleexport exporter first" >&2
    exit 1
fi
if [ ! -f "$SITE_SRC/Site.reds" ]; then
    echo "ERROR: $SITE_SRC/Site.reds missing — run scripts/gen-exalted-reds.py first" >&2
    exit 1
fi

# --- language tag validation -------------------------------------------------
# Validate the SKIP_CET enum first, on its own, so a typo is rejected the same
# way whether or not a language tag is present.
case "$SKIP_CET" in
    0|1) ;;
    *)
        echo "ERROR: EXALTED_SKIP_CET must be 0 or 1 (got '$SKIP_CET')" >&2
        exit 1
        ;;
esac

# The tag lands in the zip FILENAME and is the only thing distinguishing a
# language artifact from the English one, so it must be boring.
if [ -n "$LANG_TAG" ]; then
    case "$LANG_TAG" in
        *[!a-z0-9]* | [!a-z]*)
            echo "ERROR: EXALTED_LANG_TAG='$LANG_TAG' must be lowercase ASCII alphanumeric (e.g. es, por, zh)" >&2
            exit 1
            ;;
    esac
    # A language browser payload plus the ENGLISH CET tree is not a valid
    # artifact: it would be named as the language but silently overwrite the
    # shipped unified/CET zips, which carry no language tag. Refuse it.
    if [ "$SKIP_CET" != "1" ]; then
        echo "ERROR: EXALTED_LANG_TAG=$LANG_TAG requires EXALTED_SKIP_CET=1." >&2
        echo "       The CET surface reads cet/EXALTED/data/ and is English-only;" >&2
        echo "       packaging it with a $LANG_TAG browser payload would overwrite" >&2
        echo "       $CET_ZIP and $CET_ONLY_ZIP with an untagged, mixed-language build." >&2
        exit 1
    fi
fi

# --- URL-slug gate -----------------------------------------------------------
# ExaltedBookShort() values are interpolated straight into in-game URLs:
#   Site.reds:300  NETdir://exalted.terminal/b/<short>
#   Site.reds:340  NETdir://exalted.terminal/r/<short>/<ch>:<vp>
# and parsed back by EXAL_TakeFirstPath()/EXAL_FindBook() (Site.reds:120-137),
# which splits on '/' and compares with Equals(). So a slug carrying a space,
# an accent or any non-ASCII glyph ships a dead address. The Spanish pilot hit
# exactly this: 37/66 PDF-derived names ("2 Cronicas", "Generesis") were being
# used as slugs until they were replaced with the canonical KJV ones.
#
# Slugs are therefore a LANGUAGE-INDEPENDENT, ASCII-only namespace and must
# equal the canonical KJV short for the same book number — that is what keeps
# /b/<short> addresses valid across languages and lets a future multi-language
# pack share one route space. This gate runs on EVERY build (English included),
# so no language can bypass it.
python3 - "$SITE_SRC/data" "$CANON_BOOKS" "${LANG_TAG:-en}" <<'PY' || exit 1
import glob
import json
import os
import re
import sys

data, canon_path, tag = sys.argv[1], sys.argv[2], sys.argv[3]
master = os.path.join(data, "ExaltedData.reds")

# Route-safe = ASCII letters/digits only. Verified against all 66 canonical
# KJV slugs (Gen, 1Chr, 2Thess, Philem ...), so this is not a new restriction:
# canonical slugs are all alphanumeric, all unique, and at most 6 chars. The
# bound below is deliberately looser than that — exactness is enforced by the
# equality check against canonical books.json, not by this pattern.
SLUG_RE = re.compile(r"^[A-Za-z0-9]{1,12}$")
CASE_RE = re.compile(r'^\s*case (\d+): return s"(.*)";\s*$')

errors = []


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


if not os.path.isfile(master):
    sys.exit(
        f"ERROR [{tag}]: {master} missing — the site tree has no generated data.\n"
        f"       Run scripts/gen-exalted-reds.py --out <site tree>/data first."
    )

text = open(master, encoding="utf-8").read()
names = cases(text, "ExaltedBookName")
shorts = cases(text, "ExaltedBookShort")
if shorts is None:
    sys.exit(f"ERROR [{tag}]: ExaltedBookShort() not found in {master} (stale or hand-edited generator output?)")
if names is None:
    sys.exit(f"ERROR [{tag}]: ExaltedBookName() not found in {master}")

if set(names) != set(shorts):
    only_n = sorted(set(names) - set(shorts))
    only_s = sorted(set(shorts) - set(names))
    sys.exit(f"ERROR [{tag}]: ExaltedBookName/Short cover different books "
             f"(name-only {only_n}, short-only {only_s}) — {master} is inconsistent")

nums = sorted(shorts)
expect_nums = list(range(1, len(nums) + 1))
if nums != expect_nums:
    sys.exit(f"ERROR [{tag}]: book numbers are not contiguous 1..N in {master} (got {nums[:5]}...{nums[-3:]})")

canon = json.load(open(canon_path, encoding="utf-8"))
canon_short = {int(b["n"]): b["short"] for b in canon}
canon_all_shorts = {b["short"] for b in canon}

# SUBCANON GATE. The positional check below (short[n] == canon_short[n]) is the
# strongest possible check and is exactly right for a full 66-book build, so it
# is NOT relaxed. But a 39-book Tanakh is a different canon: it numbers Malachi
# 26 where the KJV canon numbers it 39, so its 39 correct canonical slugs sit at
# positions that will never line up with canon_short[n]. Matching positionally
# there would demand the WRONG slug (it wanted s"Nah" to be Eccl) -- i.e. it
# would have driven us into the mislabelling trap the anchors exist to catch.
#
# For a sub-canon build the equivalent guarantee is: every slug is a canonical
# KJV short, all are unique, and the set is exactly the canonical OT subset
# (KJV books 1..39). That is still provably strict -- no invented, misnumbered
# or duplicate slug can pass.
OT_CANON_N = 39
subcanon = len(nums) != 66
if subcanon:
    ot_expected = {canon_short[n] for n in range(1, OT_CANON_N + 1)}
    subcanon_ok = set(shorts.values()) == ot_expected
    if not subcanon_ok:
        missing = sorted(ot_expected - set(shorts.values()))
        extra = sorted(set(shorts.values()) - ot_expected)
        errors.append(
            f"sub-canon ({len(nums)} books) slug set is not the canonical OT "
            f"set of {OT_CANON_N}: missing={missing[:6]} extra={extra[:6]}"
        )
    if len(set(shorts.values())) != len(nums):
        errors.append("sub-canon build has duplicate slugs")

# The declared total must match the number of cases actually emitted, or the
# reader loops over books that do not exist.
m = re.search(r"public func ExaltedBookTotal\(\) -> Int32 \{ return (\d+); \}", text)
if not m:
    errors.append("ExaltedBookTotal() missing or malformed")
elif int(m.group(1)) != len(nums):
    errors.append(f"ExaltedBookTotal() says {m.group(1)} but {len(nums)} book cases are emitted")

# One module per book; a half-copied data/ tree would otherwise ship silently.
mods = sorted(glob.glob(os.path.join(data, "ExaltedBook*.reds")))
if len(mods) != len(nums):
    errors.append(f"{len(mods)} ExaltedBook*.reds modules present but {len(nums)} books declared")

for n in nums:
    s = shorts[n]
    nm = names[n]
    if not s:
        errors.append(f"book {n}: empty slug")
    elif not SLUG_RE.match(s):
        why = []
        if any(ord(c) > 127 for c in s):
            why.append("non-ASCII")
        if any(c.isspace() for c in s):
            why.append("contains whitespace")
        bad = sorted({c for c in s if not c.isalnum() and ord(c) < 128})
        if bad:
            why.append("URL-unsafe " + "".join(bad))
        errors.append(
            f'book {n} ({nm}): slug s"{s}" is not route-safe ({", ".join(why)})'
            f' -> would ship NETdir://exalted.terminal/b/{s}'
        )
    elif n in canon_short and s != canon_short[n] and not subcanon:
        errors.append(
            f'book {n} ({nm}): slug s"{s}" != canonical KJV slug s"{canon_short[n]}"'
            f" — /b/<short> must resolve in every language"
        )
    elif s not in canon_all_shorts:
        errors.append(
            f'book {n} ({nm}): slug s"{s}" is not a canonical KJV book short'
            f" — /b/<short> must resolve in every language"
        )
    if not nm.strip():
        errors.append(f"book {n}: empty display name")

if errors:
    print(f"ERROR [{tag}]: URL-slug gate FAILED — {len(errors)} problem(s):", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    print("       Slugs come from the canonical KJV books.json; display names "
          "may be native.", file=sys.stderr)
    sys.exit(1)

print(f"  slug gate ok [{tag}]: {len(nums)} books, "
      f"{len(set(shorts.values()))} unique ASCII slugs, all canonical KJV")
PY


mkdir -p "$DIST"

pack() { # $1=zip name (with .zip), then game-relative dirs under $STAGE to include
    local name="$1"; shift
    rm -f "$DIST/$name" "$DIST/$name.sha256"
    (cd "$STAGE" && zip -qry "$DIST/$name" "$@")
    (cd "$DIST" && sha256sum "$name" > "$name.sha256")
}

# CET surface tree
CETTREE="$STAGE/bin/x64/plugins/cyber_engine_tweaks/mods/EXALTED"
mkdir -p "$CETTREE"
cp -r "$REPO/cet/EXALTED/." "$CETTREE/"

# Browser site tree (redscript under r6/scripts/EXALTED/)
BROWSERTREE="$STAGE/r6/scripts/EXALTED"
mkdir -p "$BROWSERTREE"
cp -r "$SITE_SRC/." "$BROWSERTREE/"

# --- offline gate -------------------------------------------------------------
# The project is offline-only (user directive 2026-10-05): no publishing surface,
# no remote, and nothing in a shipped artifact that points at an online service.
# This gate runs on EVERY build, like the slug gate above, so a URL or a network
# call cannot re-enter through a data or credit file unnoticed.
#
# What is rejected:
#   1. any http:// or https:// literal;
#   2. any bare reference to a known online host, e.g. github.com or
#      nexusmods.com without a scheme (a scheme-less host slipped past an
#      earlier http://-only sweep, so this form is checked explicitly);
#   3. network API names in code — the mod must never open a socket.
#
# MIT attribution notices keep their project NAMES here (cet/EXALTED/CREDITS.txt
# credits "Cyber Engine Tweaks" and "Dear ImGui"); only the addresses are gone.
# NETdir:// is deliberately NOT rejected: it is the game's own in-memory virtual
# filesystem, not a network protocol.
python3 - "$STAGE" "${LANG_TAG:-en}" <<'PY' || exit 1
import os
import re
import sys

stage, tag = sys.argv[1], sys.argv[2]

TEXT_EXT = {".reds", ".lua", ".txt", ".json", ".md", ".yml", ".yaml", ".xml", ".cfg", ".ini"}
SCAN_EXT = TEXT_EXT | {".sh", ".py", ""}
# Extensions that legitimately contain Bible source markup or credentials-free
# third-party notices are still scanned; nothing is exempt except binaries.
SKIP_DIRS = {".git", "__pycache__", ".ruff_cache"}

URL_RE = re.compile(r"https?://", re.I)
# Hosts that mean "this artifact points at an online service". Matched WITHOUT a
# scheme too, so a bare host cannot hide from the check above.
HOSTS = (
    "github.com", "githubusercontent.com", "gitlab.com", "nexusmods.com",
    "redmodding.org", "nativedb", "mechon-mamre.org", "tanach.us",
    "thaipope.org", "gutenberg.org", "ebible.org", "eBible.org",
    "wikipedia.org", "creativecommons.org", "s3.amazonaws.com",
)
API_RE = re.compile(
    r"\b(curl|wget|HttpClient|urllib|requests\.|socket\.|XMLHttpRequest|"
    r"WebSocket|io\.popen|os\.system)\b"
)


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            yield os.path.join(dirpath, fn)


errors = []
checked = 0
for path in walk(stage):
    ext = os.path.splitext(path)[1].lower()
    if ext not in SCAN_EXT:
        continue
    try:
        text = open(path, "r", encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        continue  # binary or unreadable: not a place a URL could hide as text
    checked += 1
    rel = os.path.relpath(path, stage)
    for lineno, line in enumerate(text.splitlines(), 1):
        if URL_RE.search(line):
            errors.append(f"{rel}:{lineno}: http(s) URL — {line.strip()[:70]}")
        for host in HOSTS:
            if host.lower() in line.lower():
                errors.append(f"{rel}:{lineno}: online host '{host}' — {line.strip()[:70]}")
        if ext in TEXT_EXT and API_RE.search(line):
            errors.append(f"{rel}:{lineno}: network API — {line.strip()[:70]}")

if errors:
    print(f"ERROR [{tag}]: offline gate FAILED — {len(errors)} problem(s):", file=sys.stderr)
    for e in errors[:40]:
        print(f"  - {e}", file=sys.stderr)
    if len(errors) > 40:
        print(f"  ... and {len(errors) - 40} more", file=sys.stderr)
    print("       The project is offline-only. Shipping artifacts carry no URLs,", file=sys.stderr)
    print("       no online hosts, and no network calls.", file=sys.stderr)
    sys.exit(1)

print(f"  offline gate ok [{tag}]: {checked} text file(s), no URLs, hosts or network calls")
PY
if [ "$SKIP_CET" = "1" ]; then
    pack "$BROWSER_ZIP" "r6"
    echo "Packed (browser only${LANG_PART:+, language$LANG_PART}):"
    cat "$DIST/$BROWSER_ZIP.sha256"
    exit 0
fi

pack "$CET_ZIP" "bin" "r6"
pack "$CET_ONLY_ZIP" "bin"
pack "$BROWSER_ZIP" "r6"

echo "Packed:"
cat "$DIST/$CET_ZIP.sha256"
cat "$DIST/$CET_ONLY_ZIP.sha256"
cat "$DIST/$BROWSER_ZIP.sha256"