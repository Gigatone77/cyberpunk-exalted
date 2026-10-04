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
# Translation pilot overrides (used for the Spanish Browser build) so a second
# language can be packaged WITHOUT touching the shipped English tree:
#   EXALTED_SITE_SRC — browser site source tree (default internet/EXALTED)
#   EXALTED_LANG_TAG — language slug appended to the browser zip name
#                      (e.g. "es" -> EXALTED_Terminal_77-Browser-es-0.1.2.zip)
#   EXALTED_SKIP_CET — set to 1 to build only the browser zip (CET is English)
#
# NOTE: the CET surface reads cet/EXALTED/data/ directly and is still
# English-only; a translated CET surface needs its own cache.lua build.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$REPO/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

CET_VERSION="${EXALTED_VERSION:-$(sed -n 's/^[[:space:]]*version[[:space:]]*=[[:space:]]*"\([0-9.]*\)".*/\1/p' "$REPO/cet/EXALTED/init.lua" | head -n1)}"
CET_VERSION="${CET_VERSION:-0.1.5}"
BROWSER_VERSION="${EXALTED_BROWSER_VERSION:-0.1.2}"
SITE_SRC="${EXALTED_SITE_SRC:-$REPO/internet/EXALTED}"
LANG_TAG="${EXALTED_LANG_TAG:-}"
SKIP_CET="${EXALTED_SKIP_CET:-0}"

LANG_PART=""
[ -n "$LANG_TAG" ] && LANG_PART="-$LANG_TAG"

CET_ZIP="EXALTED_Terminal_77-${CET_VERSION}.zip"
CET_ONLY_ZIP="EXALTED_Terminal_77-CET-${CET_VERSION}.zip"
BROWSER_ZIP="EXALTED_Terminal_77-Browser${LANG_PART}-${BROWSER_VERSION}.zip"

if [ ! -f "$REPO/cet/EXALTED/data/books.json" ]; then
    echo "ERROR: data/books.json missing — run the bibleexport exporter first" >&2
    exit 1
fi
if [ ! -f "$SITE_SRC/Site.reds" ]; then
    echo "ERROR: $SITE_SRC/Site.reds missing — run scripts/gen-exalted-reds.py first" >&2
    exit 1
fi

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

if [ "$SKIP_CET" = "1" ]; then
    pack "$BROWSER_ZIP" "r6"
    echo "Packed (browser only):"
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