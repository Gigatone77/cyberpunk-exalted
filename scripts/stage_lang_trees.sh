#!/usr/bin/env bash
# Stage the six SHIPPABLE language trees for scripts/langify.py.
#
# Sources are the already-verified, already-shipped artifacts -- never the raw
# Bible files, which are immutable and must not be read for text or rewritten.
#   en  internet/EXALTED/data          (repo English build)
#   cze deu dut pol  ~/bible-sources/site/<code>/data   (generated trees)
#   es  dist/EXALTED_Terminal_77-Browser-es-0.1.2.zip  (Spanish has no
#        bible-sources/site tree; the shipped zip is the verified artifact)
#
# Usage: scripts/stage_lang_trees.sh [STAGE_DIR]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIBLE="$HOME/bible-sources"
STAGE="${1:-$HOME/gt-probe/mlstage}"
LANGS="en es cze deu dut pol"

for c in $LANGS; do
  command -v python3 >/dev/null || { echo "need python3" >&2; exit 1; }
done

rm -rf "$STAGE"
mkdir -p "$STAGE"

for L in en es cze deu dut pol; do
  mkdir -p "$STAGE/$L"
  case "$L" in
    es)
      ZIP="$ROOT/dist/EXALTED_Terminal_77-Browser-es-0.1.2.zip"
      [ -f "$ZIP" ] || { echo "missing $ZIP (build it first)" >&2; exit 1; }
      tmp=$(mktemp -d)
      unzip -q "$ZIP" -d "$tmp"
      cp -r "$tmp/r6/scripts/EXALTED/data" "$STAGE/$L/data"
      rm -rf "$tmp"
      ;;
    cze|deu|dut|pol)
      SRC="$BIBLE/site/$L/data"
      [ -d "$SRC" ] || { echo "missing $SRC (run scripts/build_lang.sh $L)" >&2; exit 1; }
      cp -r "$SRC" "$STAGE/$L/data"
      ;;
    en)
      cp -r "$ROOT/internet/EXALTED/data" "$STAGE/$L/data"
      ;;
  esac
  n=$(ls -1 "$STAGE/$L"/data/ExaltedBook*.reds 2>/dev/null | wc -l)
  [ "$n" = 66 ] || { echo "$L: expected 66 book modules, got $n" >&2; exit 1; }
  [ -f "$STAGE/$L/data/ExaltedData.reds" ] || { echo "$L: no ExaltedData.reds" >&2; exit 1; }
  printf 'staged %-4s 66 book modules + ExaltedData\n' "$L"
done

echo "stage ready: $STAGE"