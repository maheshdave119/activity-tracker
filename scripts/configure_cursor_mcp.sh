#!/usr/bin/env bash
set -euo pipefail
BASE="$HOME/.local/share/cursor-only-activity-tracker"
VENV="$BASE/venv"; APP="$BASE/app"; CFG="$HOME/.cursor"
mkdir -p "$CFG"
python3 - "$CFG/mcp.json" "$VENV/bin/python" "$APP" "$BASE" <<'PY'
import json,sys,os
path,python,app,base=sys.argv[1:]
data={}
if os.path.exists(path):
    try:
        with open(path) as f: data=json.load(f)
    except Exception: pass
data.setdefault("mcpServers",{})["cursor-only-activity-tracker"]={
  "command":python,
  "args":["-m","tracker.mcp_server"],
  "cwd":app,
  "env":{"PYTHONPATH":app,"TRACKER_DATA_DIR":base}
}
with open(path,"w") as f: json.dump(data,f,indent=2)
print("Updated",path)
PY
echo "Restart Cursor to load the cursor-only-activity-tracker MCP server."
