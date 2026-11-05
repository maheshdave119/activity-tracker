#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_HOME="$HOME/.cursor/extensions"
DEST="$EXT_HOME/local-activity-tools.cursor-local-activity-collector-1.1.0"
mkdir -p "$EXT_HOME"
rm -rf "$DEST"
mkdir -p "$DEST"
cp "$ROOT/cursor-extension/package.json" "$ROOT/cursor-extension/extension.js" "$DEST/"
echo "Installed Cursor Local Activity Collector to: $DEST"
echo "Restart Cursor completely (all windows) to activate it."
echo "The extension sends activity metadata only to http://127.0.0.1:8766."
