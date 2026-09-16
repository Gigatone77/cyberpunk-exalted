#!/usr/bin/env bash
# Start the EXALTED host bridge for the installed mod. Runs in the foreground;
# keep it running while you play. Requires: install.sh already run.
set -euo pipefail

MODS_DIR="${1:-$HOME/Games/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods}"
TARGET="$MODS_DIR/EXALTED"
BIN="$TARGET/bin/exalted"

if [ ! -x "$BIN" ]; then
    echo "ERROR: $BIN not found — run scripts/install.sh" >&2
    exit 1
fi

echo "EXALTED bridge watching $TARGET (Ctrl-C to stop)"
"$BIN" bridge --dir "$TARGET" --interval 150