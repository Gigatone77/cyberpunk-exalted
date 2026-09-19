#!/usr/bin/env bash
# Package the mod as Nexus-style zips: game-relative trees at the zip root
# so extracting into the game root installs them — like standard CP2077
# Nexus mods. Pure Lua + pure redscript: data ships inside, no host binary.
#
# Produces three zips:
#   EXALTED_Terminal_77-0.1.3.zip        — UNIFIED (CET + browser site)
#   EXALTED_Terminal_77-CET-0.1.3.zip    — CET surface only
#   EXALTED_Terminal_77-Browser-0.1.0.zip — in-game browser site only
#
# Version overrides via env: EXALTED_VERSION (CET, default from init.lua),
# EXALTED_BROWSER_VERSION (browser site, default 0.1.0).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$REPO/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

CET_VERSION="${EXALTED_VERSION:-$(sed -n 's/^[[:space:]]*version[[:space:]]*=[[:space:]]*"\([0-9.]*\)".*/\1/p' "$REPO/cet/EXALTED/init.lua" | head -n1)}"
CET_VERSION="${CET_VERSION:-0.1.3}"
BROWSER_VERSION="${EXALTED_BROWSER_VERSION:-0.1.0}"

CET_ZIP="EXALTED_Terminal_77-${CET_VERSION}.zip"
CET_ONLY_ZIP="EXALTED_Terminal_77-CET-${CET_VERSION}.zip"
BROWSER_ZIP="EXALTED_Terminal_77-Browser-${BROWSER_VERSION}.zip"

if [ ! -f "$REPO/cet/EXALTED/data/books.json" ]; then
    echo "ERROR: data/books.json missing — run the bibleexport exporter first" >&2
    exit 1
fi
if [ ! -f "$REPO/internet/EXALTED/Site.reds" ]; then
    echo "ERROR: internet/EXALTED/Site.reds missing — run scripts/gen-exalted-reds.py first" >&2
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
cp -r "$REPO/internet/EXALTED/." "$BROWSERTREE/"

pack "$CET_ZIP" "bin" "r6"
pack "$CET_ONLY_ZIP" "bin"
pack "$BROWSER_ZIP" "r6"

echo "Packed:"
cat "$DIST/$CET_ZIP.sha256"
cat "$DIST/$CET_ONLY_ZIP.sha256"
cat "$DIST/$BROWSER_ZIP.sha256"