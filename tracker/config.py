import os
from pathlib import Path

DATA = Path(os.getenv("TRACKER_DATA_DIR", "~/.local/share/cursor-only-activity-tracker")).expanduser()
DB_PATH = DATA / "tracker.sqlite3"
ROOTS = [Path(x.strip()).expanduser().resolve() for x in os.getenv(
    "TRACKER_WORKSPACE_ROOTS", "~/Projects,~/htdocs"
).split(",") if x.strip()]
SCAN_INTERVAL = max(10, int(os.getenv("TRACKER_SCAN_INTERVAL", "30")))
IDLE_THRESHOLD = max(60, int(os.getenv("TRACKER_IDLE_THRESHOLD_SECONDS", "300")))
EXCLUDES = set(os.getenv(
    "TRACKER_EXCLUDE_DIRS", ".git,node_modules,vendor,.venv,venv,dist,build,.next,.idea"
).split(","))

# Activity source. The dashboard talks to this interface, not to one product.
# The default server is the Cursor timelog MCP; point these at another MCP later.
def _default_mcp_pythonpath() -> str:
    sibling = Path(__file__).resolve().parents[2] / "cursor-timelog-mcp"
    if (sibling / "cursor_timelog" / "server.py").is_file():
        return str(sibling)
    installed = Path.home() / ".local/share/cursor-timelog-mcp"
    if (installed / "cursor_timelog" / "server.py").is_file():
        return str(installed)
    return ""

def _default_mcp_command() -> str:
    installed = Path.home() / ".local/share/cursor-timelog-mcp/.venv/bin/python"
    return str(installed) if installed.is_file() else "python3"

ACTIVITY_MCP_COMMAND = os.getenv("ACTIVITY_MCP_COMMAND", _default_mcp_command())
ACTIVITY_MCP_ARGS = os.getenv("ACTIVITY_MCP_ARGS", "-m cursor_timelog.server")
ACTIVITY_MCP_PYTHONPATH = os.getenv("ACTIVITY_MCP_PYTHONPATH", _default_mcp_pythonpath())
ACTIVITY_MCP_TOOL = os.getenv("ACTIVITY_MCP_TOOL", "generate_timelog")
ACTIVITY_MCP_CWD = os.getenv("ACTIVITY_MCP_CWD", "")
