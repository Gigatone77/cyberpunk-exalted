#!/usr/bin/env bash
# Package the mod as a single Nexus-style zip: the CET mod under the
# GAME-RELATIVE tree at the zip root (bin/x64/plugins/cyber_engine_tweaks/
# mods/EXALTED/…), so extracting it into the game root installs it in the
# right place — like standard Cyberpunk 2077 Nexus mods. Pure Lua: data
# ships inside the mod folder, no host bridge binary.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${EXALTED_VERSION:-0.1.0}"
NAME="EXALTED_Terminal_77-${VERSION}"
DIST="$REPO/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

if [ ! -f "$REPO/cet/EXALTED/data/books.json" ]; then
    echo "ERROR: data/books.json missing — run the bibleexport exporter first" >&2
    exit 1
fi

mkdir -p "$DIST"
rm -f "$DIST/$NAME.zip" "$DIST/$NAME.zip.sha256"
MODTREE="$STAGE/bin/x64/plugins/cyber_engine_tweaks/mods/EXALTED"
mkdir -p "$MODTREE"
cp -r "$REPO/cet/EXALTED/." "$MODTREE/"

(cd "$STAGE" && zip -qr "$DIST/$NAME.zip" "bin")
(cd "$DIST" && sha256sum "$NAME.zip" > "$NAME.zip.sha256")

echo "Packed: $DIST/$NAME.zip"
cat "$DIST/$NAME.zip.sha256"