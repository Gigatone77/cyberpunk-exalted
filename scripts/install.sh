#!/usr/bin/env bash
# Install the EXALTED Terminal mod into Cyberpunk 2077's CET mods folder and
# stage the host bridge binary inside the mod folder (self-contained).
#
# Usage:
#   ./install.sh [MODS_DIR]
#   (default: $HOME/Games/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC_MOD="$REPO/cet/EXALTED"
SRC_BIN="$REPO/bin/exalted"
MODS_DIR="${1:-$HOME/Games/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods}"
TARGET="$MODS_DIR/EXALTED"

if [ ! -d "$MODS_DIR" ]; then
    echo "ERROR: mods dir not found: $MODS_DIR" >&2
    echo "Pass the correct path: $0 <path-to-mod-X64>/plugins/cyber_engine_tweaks/mods" >&2
    exit 1
fi
if [ ! -x "$SRC_BIN" ]; then
    echo "ERROR: host binary missing — run scripts/build.sh first." >&2
    exit 1
fi

if [ -e "$TARGET" ]; then
    echo "NOTE: $TARGET already exists — backing it up before overwrite."
    ts="$(date +%Y%m%d-%H%M%S)"
    mv "$TARGET" "$TARGET.bak-$ts"
fi

mkdir -p "$TARGET"
cp -r "$SRC_MOD/." "$TARGET/"
mkdir -p "$TARGET/bin"
cp "$SRC_BIN" "$TARGET/bin/exalted"
chmod +x "$TARGET/bin/exalted"

echo "Installed: $TARGET"
echo
echo "Start the host bridge (needed for data/notes/memory):"
echo "  $TARGET/bin/exalted bridge --dir \"$TARGET\""
echo
echo "Then in game: use the CET Overlay -> 'MODS?' panel to bind hotkeys"
echo "for OPEN_EXALTED_TERMINAL and OPEN_EXALTED_BOOK."