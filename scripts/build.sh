#!/usr/bin/env bash
# Build the `exalted bridge` Host binary and stage it into the repo's bin/.
# The game mod runs in the game; the binary runs on the Linux host and speaks
# to the mod through commands.json / responses.json in the mod folder.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${EXALTED_SRC:-$HOME/Games/biblelearn}"
VERSION="${EXALTED_VERSION:-0.1.0}"
GO_BIN="${GO_BIN:-$HOME/.local/go/bin/go}"

if [ ! -x "$GO_BIN" ]; then
    GO_BIN="$(command -v go || true)"
fi
if [ -z "$GO_BIN" ]; then
    echo "ERROR: no Go toolchain found (looked for \$HOME/.local/go/bin/go)." >&2
    exit 1
fi

echo "Building exalted ${VERSION} from ${SRC} ..."
(cd "$SRC" && "$GO_BIN" build -trimpath -ldflags "-s -w -X main.version=${VERSION}" -o "$REPO/bin/exalted" ./cmd/biblelearn)

echo "Binary: $REPO/bin/exalted  ($(du -h "$REPO/bin/exalted" | cut -f1))"
"$REPO/bin/exalted" version