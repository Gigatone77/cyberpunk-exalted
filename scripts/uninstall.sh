#!/usr/bin/env bash
# Uninstall EXALTED Terminal by moving it to a restorable backup (data, notes
# and memory included) — never deletes anything.
#
# Usage: ./uninstall.sh [MODS_DIR]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
MODS_DIR="${1:-$HOME/Games/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods}"
TARGET="$MODS_DIR/EXALTED"

if [ ! -e "$TARGET" ]; then
    echo "Nothing installed at $TARGET"
    exit 0
fi

BACKUP="$HOME/.local/share/exalted-backup/EXALTED-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$(dirname "$BACKUP")"
mv "$TARGET" "$BACKUP"
echo "Moved mod to restorable backup: $BACKUP"
echo "Restore later with:  mv \"$BACKUP\" \"$TARGET\""