#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="$HOME/.local/share/cursor-only-activity-tracker"
APP="$BASE/app"; VENV="$BASE/venv"; CFG="$HOME/.config/cursor-only-activity-tracker"
mkdir -p "$APP" "$CFG" "$HOME/.config/systemd/user"
cp -a "$ROOT/tracker" "$APP/"
cp "$ROOT/requirements.txt" "$APP/"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r "$APP/requirements.txt"
if [ ! -f "$CFG/.env" ]; then cp "$ROOT/.env.example" "$CFG/.env"; fi
cp "$ROOT/systemd/cursor-only-activity-tracker.service" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now cursor-only-activity-tracker.service
systemctl --user restart cursor-only-activity-tracker.service
"$ROOT/scripts/install_cursor_extension.sh"
echo
echo "Cursor-only dashboard: http://127.0.0.1:8766"
echo "Settings: nano $CFG/.env"
echo "Service: systemctl --user status cursor-only-activity-tracker"
echo "Logs: journalctl --user -u cursor-only-activity-tracker -f"
echo "This installation uses its own service, database, config and port."
echo "Restart Cursor completely, then verify /api/health shows extension events."
