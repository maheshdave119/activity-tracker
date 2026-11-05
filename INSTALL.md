# Install Activity Tracker on Ubuntu

The dashboard runs at http://127.0.0.1:8766. **Generate Today's Timelog** reads the Cursor Timelog MCP, so install that server first.

Project folder:

`/home/mahesh.dave@brainvire.com/htdocs/AI_Implementations/activity-tracker`

## 1. Install the Timelog MCP

Follow [cursor-timelog-mcp/INSTALL.md](../cursor-timelog-mcp/INSTALL.md) and confirm `timelog` works in Cursor before you continue.

## 2. Install Ubuntu packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip xprintidle
```

`xprintidle` is used to detect idle time. The dashboard still runs if it is missing.

## 3. Open the project

```bash
cd /home/mahesh.dave@brainvire.com/htdocs/AI_Implementations/activity-tracker
chmod +x scripts/*.sh
```

## 4. Install the dashboard and background service

```bash
./scripts/install.sh
```

This command:

- Copies the app to `~/.local/share/cursor-only-activity-tracker/app`
- Creates a virtual environment and installs the Python packages
- Creates `~/.config/cursor-only-activity-tracker/.env` from `.env.example` the first time
- Installs and starts the user service `cursor-only-activity-tracker`
- Installs the Cursor extension **Cursor Local Activity Collector**

Run this from a normal desktop login. If `systemctl --user` says it cannot connect to the bus, you are not in a user session. Log in to the Ubuntu desktop and run the command again.

To keep the service running after you log out:

```bash
sudo loginctl enable-linger "$USER"
```

## 5. Set your project folders

```bash
nano ~/.config/cursor-only-activity-tracker/.env
```

Set `TRACKER_WORKSPACE_ROOTS` to the real folders that contain your projects, separated by commas:

```env
TRACKER_WORKSPACE_ROOTS=/home/mahesh.dave@brainvire.com/htdocs
```

Save the file, then restart the service:

```bash
systemctl --user restart cursor-only-activity-tracker
```

## 6. Restart Cursor

Quit every Cursor window, then open Cursor again. The activity extension only connects after a full restart.

## 7. Open the dashboard

```bash
xdg-open http://127.0.0.1:8766
```

Or open that address in a browser.

1. Click **Generate Today's Timelog**.
2. Use the date field to open another day.
3. Use the project list to show one project.
4. Use **Copy all**, **Copy project**, or **Copy** for the text.
5. Use **Export CSV** for the date and project currently on screen.

## 8. Confirm the service

```bash
systemctl --user status cursor-only-activity-tracker
curl -s http://127.0.0.1:8766/api/health
```

`status` in the health response should be `ok`. After you use Cursor for a minute, `cursor_extension_events` should be greater than zero.

Follow the service log with:

```bash
journalctl --user -u cursor-only-activity-tracker -f
```

## Optional: register the tracker's own MCP

The dashboard does not need this. It is only for asking Cursor about the tracker's stored events.

```bash
cd /home/mahesh.dave@brainvire.com/htdocs/AI_Implementations/activity-tracker
./scripts/configure_cursor_mcp.sh
```

Restart Cursor. A server named `cursor-only-activity-tracker` appears next to `cursor-timelog`. Daily timelog text still comes from `cursor-timelog`.

## Update after you pull new code

```bash
cd /home/mahesh.dave@brainvire.com/htdocs/AI_Implementations/activity-tracker
git pull
./scripts/install.sh
```

Your existing `.env` and database are kept. Restart Cursor after the extension is copied again.

## Uninstall

```bash
cd /home/mahesh.dave@brainvire.com/htdocs/AI_Implementations/activity-tracker
./scripts/uninstall.sh
```

This stops the service and removes the Cursor extension. The database stays in `~/.local/share/cursor-only-activity-tracker`. The Timelog MCP is not removed. Use `cursor-timelog-mcp/scripts/uninstall.sh` for that.
