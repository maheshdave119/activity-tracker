#!/usr/bin/env bash
set -euo pipefail
systemctl --user disable --now cursor-only-activity-tracker.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/cursor-only-activity-tracker.service"
rm -rf "$HOME/.cursor/extensions/local-activity-tools.cursor-local-activity-collector-1.1.0"
systemctl --user daemon-reload
echo "Cursor-only service and its Cursor extension removed."
echo "Its data remains in ~/.local/share/cursor-only-activity-tracker"
echo "Your other Ubuntu activity tracker and its database are not touched."
