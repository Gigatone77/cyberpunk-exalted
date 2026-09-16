#!/usr/bin/env bash
# OPTIONAL helper: install a systemd USER service that runs the EXALTED bridge
# automatically, so the mod behaves like a drop-in CET mod (no manual steps).
# This ADDS to the manual scripts/start-bridge.sh flow; both can coexist.
#
# Usage: ./install-bridge-service.sh [MODS_DIR]
set -euo pipefail

MODS_DIR="${1:-$HOME/Games/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods}"
TARGET="$MODS_DIR/EXALTED"
UNIT="$HOME/.config/systemd/user/exalted-bridge.service"

if [ ! -x "$TARGET/bin/exalted" ]; then
    echo "ERROR: $TARGET/bin/exalted missing — run scripts/install.sh first." >&2
    exit 1
fi

mkdir -p "$(dirname "$UNIT")"
cat > "$UNIT" <<EOF
[Unit]
Description=EXALTED Terminal bridge (CP2077 CET mod IPC host)
After=graphical-session.target

[Service]
Type=simple
ExecStart="$TARGET/bin/exalted" bridge --dir "$TARGET" --interval 150
Restart=on-failure
RestartSec=2
Nice=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now exalted-bridge.service
sleep 1
systemctl --user --no-pager --lines=3 status exalted-bridge.service || true
echo
echo "Optional service installed: $UNIT"
echo "You can stop/start it anytime with:  systemctl --user stop|start exalted-bridge.service"