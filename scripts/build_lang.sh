#!/usr/bin/env bash
# Build ONE language's EXALTED in-game browser mod: generate + package.
#
# The per-language pipeline, deliberately kept to a single language per run so
# each step is bounded and a failure names the translation that caused it:
#
#   1. read the real book/chapter/verse counts out of that build's own
#      build-report.json and hand them to the generator as hard assertions
#      (gen-exalted-reds.py aborts if the emitted totals differ);
#   2. stage a per-language site tree (Site.reds chrome + generated data/);
#   3. package it through scripts/package.sh, which runs the ASCII canonical
#      slug gate before anything is zipped.
#
# Usage: scripts/build_lang.sh <lang> [--no-package]
#   <lang>        language slug, e.g. ron
#   --no-package  generate the site tree but skip zipping (for inspection)
#
# The CET surface is English-only and reads cet/EXALTED/data/, so a language
# build is browser-only (EXALTED_SKIP_CET=1) -- enforced inside package.sh.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_ROOT="${EXALTED_BUILD_ROOT:-/var/home/Gigatone/bible-sources/build}"
SITE_ROOT="${EXALTED_SITE_ROOT:-/var/home/Gigatone/bible-sources/site}"

LANG="${1:-}"
PACKAGE=1
shift || true
for a in "$@"; do
    case "$a" in
        --no-package) PACKAGE=0 ;;
        *) echo "unknown option: $a" >&2; exit 2 ;;
    esac
done

if [ -z "$LANG" ]; then
    echo "usage: scripts/build_lang.sh <lang> [--no-package]" >&2
    exit 2
fi

SRC="$BUILD_ROOT/$LANG"
REPORT="$SRC/build-report.json"
if [ ! -f "$REPORT" ]; then
    echo "ERROR: no build for '$LANG' at $SRC (missing build-report.json)" >&2
    echo "       vetted sources are listed in /var/home/Gigatone/bible-sources/VETTED.txt" >&2
    exit 1
fi

# Real totals come from the converter's own report. Passing them as --expect-*
# turns the generator's final count assertion into a real guard: if this
# translation's JSON does not parse to exactly what was converted, we abort
# instead of shipping a half-read site tree.
read -r NBOOKS NCHAP NVERS NRED < <(python3 - "$REPORT" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
print(len(r.get("books", [])), r["total_chapters"], r["total_verses"],
      r.get("red_verses", 0) or 0)
PY
)

SITE="$SITE_ROOT/$LANG"
echo "=== EXALTED language build: $LANG ==="
echo "    build    $SRC"
echo "    site     $SITE"
echo "    totals   books=$NBOOKS chapters=$NCHAP verses=$NVERS red=$NRED"

# Stage the site tree from scratch so a half-copied data/ can never ship.
# Only this script's own generated output lives here, so clearing it is safe.
rm -rf "$SITE"
mkdir -p "$SITE/data"
cp "$REPO/internet/EXALTED/Site.reds" "$SITE/Site.reds"

python3 "$REPO/scripts/gen-exalted-reds.py" \
    --src "$SRC" \
    --book-subdir '' \
    --out "$SITE/data" \
    --expect-books "$NBOOKS" \
    --expect-chapters "$NCHAP" \
    --expect-verses "$NVERS" \
    --expect-red "$NRED"

NMODS=$(find "$SITE/data" -name 'ExaltedBook*.reds' | wc -l)
echo "    generated $NMODS book modules"

if [ "$PACKAGE" = "0" ]; then
    echo "    --no-package: stopping before zip"
    exit 0
fi

EXALTED_SITE_SRC="$SITE" EXALTED_LANG_TAG="$LANG" EXALTED_SKIP_CET=1 \
    bash "$REPO/scripts/package.sh"

echo "=== $LANG done ==="