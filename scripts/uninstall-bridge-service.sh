#!/usr/bin/env bash
# Remove the optional systemd user service. Keeps the mod folder and data.
# Usage: ./uninstall-bridge-service.sh [_IGNORED_MODS_DIR_]
set -euo pipefail

UNIT="$HOME/.config/systemd/user/exalted-bridge.service"

if [ ! -f "$UNIT" ]; then
    echo "No systemd service unit present ($UNIT)"
    exit 0
fi

systemctl --user disable --now exalted-bridge.service || true
rm -f "$UNIT"
systemctl --user daemon-reload
echo "Removed: $UNIT (mod folder untouched)"