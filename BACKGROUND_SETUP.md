# BronxBot Background Service Setup

This guide will help you set up BronxBot to run silently in the background with a system tray icon.

## Features

- **Auto-start on boot** - Bot starts automatically when you login
- **Silent operation** - Runs in background with minimal console output
- **System tray management** - Control the bot from your system tray
- **Real-time monitoring** - View bot status and stats from tray icon
- **Easy log access** - View logs directly from the tray menu
- **Service management** - Start, stop, restart from tray or command line

## Quick Setup

1. **Run the setup script:**
   ```bash
   ./setup_background.sh
   ```

2. **Start the bot and tray:**
   ```bash
   ./start_bot.sh
   ./start_tray.sh
   ```

3. **Or just reboot** - Everything will start automatically!

## What Gets Installed

- **Systemd service** - Manages the bot as a background service
- **System tray app** - PyQt5-based tray icon for management
- **Auto-start entries** - Bot and tray start automatically on login
- **Convenience scripts** - Easy command-line management

## System Tray Features

Right-click the tray icon to access:

- **Status & Stats** - Current bot status and server statistics  
- **Start/Stop/Restart** - Control the bot service
- **View Logs** - Open a window with recent bot logs
- **Auto-start Management** - Enable/disable automatic startup
- **Service Control** - Full systemd service integration

## Command Line Management

After setup, you'll have these scripts:

```bash
./start_bot.sh     # Start the bot service
./stop_bot.sh      # Stop the bot service  
./status_bot.sh    # Check bot status
./logs_bot.sh      # View recent logs
./start_tray.sh    # Start system tray manually
```

## Manual Control

You can also use systemctl directly:

```bash
# Service management
systemctl --user start bronxbot
systemctl --user stop bronxbot
systemctl --user restart bronxbot
systemctl --user status bronxbot

# Auto-start management
systemctl --user enable bronxbot
systemctl --user disable bronxbot

# View logs
journalctl --user -u bronxbot -f
```

## Requirements

- Linux with systemd (Ubuntu, Fedora, Arch, etc.)
- Python 3.8+
- PyQt5 (for system tray - installed automatically)
- Desktop environment with system tray support

## Troubleshooting

**System tray not appearing:**
- Make sure you have a desktop environment running
- Install PyQt5: `pip install PyQt5`
- Some minimal desktop environments may not support system tray

**Service won't start:**
- Check logs: `./logs_bot.sh`
- Verify bot configuration: `python bronxbot.py --help`
- Check service status: `./status_bot.sh`

**Permission issues:**
- Make sure scripts are executable: `chmod +x *.sh`
- Check systemd service: `systemctl --user status bronxbot`

## Uninstalling

To remove the background service setup:

```bash
./uninstall_background.sh
```

This will:
- Stop and disable the service
- Remove systemd files
- Remove auto-start entries  
- Remove convenience scripts
- Leave the bot files intact

## Configuration

The bot runs with these optimizations for background operation:

- `--quiet` - Minimal console output
- Automatic restart on crashes
- Log rotation and management
- Reduced system resource usage
- Silent startup and shutdown

You can still run the bot manually for testing:
```bash
python bronxbot.py
```
