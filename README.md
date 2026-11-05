# Cursor-Only Activity Tracker MCP + Dashboard

A separate local application dedicated to Cursor development sessions. It does not merge with, overwrite, or reuse a general Ubuntu activity-tracking app.

## Isolation from your existing tracker

- Dashboard: `http://127.0.0.1:8766` (not 8765)
- systemd service: `cursor-only-activity-tracker.service`
- Configuration: `~/.config/cursor-only-activity-tracker/.env`
- Database: `~/.local/share/cursor-only-activity-tracker/tracker.sqlite3`
- Application: `~/.local/share/cursor-only-activity-tracker/app`
- MCP name: `cursor-only-activity-tracker`

The older application/service on port 8765 is not stopped, modified, or removed.

## Cursor activity collection (v1.1)

The package now installs a small Cursor extension in addition to the local background service. The extension reports exact workspace roots and records:

- Every workspace opened, added or removed (including multiple workspaces in one Cursor window)
- Editor/file open and navigation activity, language and active document
- Document edit activity (debounced), saves, creates, deletes and renames
- Search Editor open/change events, categorized as **Search & Research**
- Terminal opened/focused events (terminal command text is not read)
- Cursor active-session heartbeat, with the current workspace when available
- Existing idle detection and optional filesystem-change evidence while Cursor is running

This is substantially richer than filesystem polling alone. It also means a project can be tracked even when it is outside the fallback `TRACKER_WORKSPACE_ROOTS`, because the extension reports the exact workspace folder to the local service.

**Restart Cursor completely after installation.** Confirm the extension is connected at `http://127.0.0.1:8766/api/health`; `cursor_extension_events` should increase as you use Cursor. The dashboard's recent activity table should then show `cursor_extension` events and the project names.

### What Cursor does not expose reliably to third-party extensions

The extension API does not provide a universal feed of every Cursor AI chat prompt/response, built-in Search-panel query text, browser research page, or terminal command/output. Search Editor activity is captured, but ordinary Search-panel terms may not be available. The collector does not record keystrokes or source-code contents. These activities must not be presented as verified facts unless Cursor exposes them in a future supported API. Use the local MCP `record_activity` tool to add a human-readable research note when you need the exact topic/query retained.

Filesystem polling remains supporting evidence only: a file changing while Cursor is open does not prove Cursor itself caused the change.

## Ubuntu requirements

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip xprintidle
```

## Install

Extract the ZIP and enter its folder:

```bash
unzip cursor-only-activity-tracker-ubuntu.zip
cd cursor-only-activity-tracker
chmod +x scripts/*.sh
./scripts/install.sh
```

Configure the directories that contain your Cursor projects:

```bash
nano ~/.config/cursor-only-activity-tracker/.env
```

Example:

```env
TRACKER_WORKSPACE_ROOTS=/home/YOUR_USER/Projects,/home/YOUR_USER/htdocs
TRACKER_SCAN_INTERVAL=30
TRACKER_IDLE_THRESHOLD_SECONDS=300
```

Use your real absolute paths. Prefer specific project roots rather than scanning the whole home directory. Then restart:

```bash
systemctl --user restart cursor-only-activity-tracker
```

Open the separate dashboard:

<http://127.0.0.1:8766>

## Daily timelog

The dashboard generates the timelog from a connected MCP server, not from the local event table. The default server is the Cursor timelog MCP (`generate_timelog`). To connect a different server later, set `ACTIVITY_MCP_COMMAND`, `ACTIVITY_MCP_ARGS`, `ACTIVITY_MCP_PYTHONPATH` and `ACTIVITY_MCP_TOOL` in the config file. The tool should return projects with tasks (description, time, hours) or the Cursor timelog shape.

Use **Generate Today's Timelog**, the date field, and the project filter. **Copy all**, **Copy project** and **Copy** use the rows on screen. **Export CSV** downloads the same date and project filter. Hours are approximate. A date with no recorded activity shows an empty state.

## Install / repair the Cursor extension separately

If the service is already installed, run this from the extracted project folder:

```bash
./scripts/install_cursor_extension.sh
```

Then completely quit and reopen Cursor. If the extension is not detected, open Cursor's Extensions view and check for **Cursor Local Activity Collector**.

## Configure Cursor MCP

From the extracted ZIP directory:

```bash
./scripts/configure_cursor_mcp.sh
```

Restart Cursor. The MCP server and dashboard use the same dedicated database.

## Available MCP tools

- `get_today_activity`
- `get_activity_by_project`
- `generate_today_timelog`
- `generate_project_timelog`
- `search_timelogs`
- `get_timelog_history`
- `get_workspace_projects`
- `get_activity_summary`
- `get_activity_for_date`
- `record_activity` (manually record an exact research/search topic or activity summary)

Example prompts in Cursor: "Generate today's timelog", "Show today's activity", "Search timelogs for API integration", or "Show activity for the last 7 days".

## Service commands

```bash
systemctl --user status cursor-only-activity-tracker
systemctl --user restart cursor-only-activity-tracker
systemctl --user stop cursor-only-activity-tracker
journalctl --user -u cursor-only-activity-tracker -f
```

## Data and uninstall

The database is stored at `~/.local/share/cursor-only-activity-tracker/tracker.sqlite3`.

To uninstall only this app:

```bash
./scripts/uninstall.sh
```

This deliberately leaves the database in place and does not touch your existing Ubuntu tracking application.

## Accuracy notes

Durations are estimates from bounded evidence windows; they are not verified billable hours. Idle detection uses `xprintidle` where the desktop session supports it. Wayland may restrict idle queries. Review evidence and idle periods before approving client timesheets.
