#!/bin/bash
# BronxBot Background Service Uninstall Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="bronxbot"
TRAY_DESKTOP_FILE="$HOME/.config/autostart/bronxbot-tray.desktop"

echo "BronxBot Background Service Uninstaller"
echo "==========================================="

# Stop and disable service
echo "Stopping and disabling service..."
systemctl --user stop $SERVICE_NAME 2>/dev/null || echo "Service was not running"
systemctl --user disable $SERVICE_NAME 2>/dev/null || echo "Service was not enabled"

# Remove service file
if [ -f "$HOME/.config/systemd/user/bronxbot.service" ]; then
    rm "$HOME/.config/systemd/user/bronxbot.service"
    echo "Removed systemd service file"
fi

# Reload systemd
systemctl --user daemon-reload

# Remove autostart desktop file
if [ -f "$TRAY_DESKTOP_FILE" ]; then
    rm "$TRAY_DESKTOP_FILE"
    echo "Removed system tray auto-start"
fi

# Remove convenience scripts
for script in start_bot.sh stop_bot.sh status_bot.sh logs_bot.sh start_tray.sh; do
    if [ -f "$SCRIPT_DIR/$script" ]; then
        rm "$SCRIPT_DIR/$script"
        echo "Removed $script"
    fi
done
# Remove virtual environment if it exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    rm -rf "$SCRIPT_DIR/venv"
    echo "Removed virtual environment"
