#!/bin/bash
# BronxBot Setup Script - Sets up the bot to run as a background service with system tray

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="bronxbot"
TRAY_DESKTOP_FILE="$HOME/.config/autostart/bronxbot-tray.desktop"

echo "BronxBot Background Service Setup"
echo "=================================="

# Check if Python virtual environment exists
VENV_PATH=""
if [ -d "$SCRIPT_DIR/venv" ]; then
    VENV_PATH="$SCRIPT_DIR/venv"
elif [ -d "/home/ks/bronx-venv" ]; then
    VENV_PATH="/home/ks/bronx-venv"
elif [ -d "$HOME/bronx-venv" ]; then
    VENV_PATH="$HOME/bronx-venv"
else
    echo "ERROR: Virtual environment not found!"
    echo "Looking for virtual environment in:"
    echo "  - $SCRIPT_DIR/venv"
    echo "  - /home/ks/bronx-venv"
    echo "  - $HOME/bronx-venv"
    echo ""
    echo "Please create a virtual environment first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate" 
    echo "  pip install -r requirements.txt"
    echo ""
    echo "Or if you have one elsewhere, create a symlink:"
    echo "  ln -s /path/to/your/venv $SCRIPT_DIR/venv"
    exit 1
fi

echo "SUCCESS: Virtual environment found at: $VENV_PATH"

# Install PyQt5 for system tray
echo "Installing PyQt5 for system tray..."
$VENV_PATH/bin/pip install PyQt5 > /dev/null 2>&1 || {
    echo "WARNING: Failed to install PyQt5, tray functionality may not work"
}

# Make scripts executable
chmod +x "$SCRIPT_DIR/bronxbot_tray.py"
echo "SUCCESS: Made tray script executable"

# Install systemd service for user
echo "Setting up systemd service..."

# Copy service file to user systemd directory
mkdir -p "$HOME/.config/systemd/user"
cp "$SCRIPT_DIR/bronxbot.service" "$HOME/.config/systemd/user/"

# Update service file with correct paths
sed -i "s|/home/ks/bronx-nextcord|$SCRIPT_DIR|g" "$HOME/.config/systemd/user/bronxbot.service"
sed -i "s|/home/ks/bronx-venv|$VENV_PATH|g" "$HOME/.config/systemd/user/bronxbot.service"

# Reload systemd and enable service
systemctl --user daemon-reload
systemctl --user enable $SERVICE_NAME

echo "SUCCESS: Systemd service installed and enabled"

# Create desktop entry for system tray auto-start
echo "Setting up system tray auto-start..."
mkdir -p "$HOME/.config/autostart"

cat > "$TRAY_DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=BronxBot Tray
Comment=BronxBot Discord Bot System Tray Manager
Exec=$VENV_PATH/bin/python $SCRIPT_DIR/bronxbot_tray.py
Icon=applications-internet
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
Terminal=false
Categories=Network;
EOF

echo "SUCCESS: System tray auto-start configured"

# Create convenience scripts
echo "Creating convenience scripts..."

# Start script
cat > "$SCRIPT_DIR/start_bot.sh" << 'EOF'
#!/bin/bash
systemctl --user start bronxbot
echo "SUCCESS: BronxBot started"
systemctl --user status bronxbot --no-pager -l
EOF

# Stop script  
cat > "$SCRIPT_DIR/stop_bot.sh" << 'EOF'
#!/bin/bash
systemctl --user stop bronxbot
echo "STOPPED: BronxBot stopped"
EOF

# Status script
cat > "$SCRIPT_DIR/status_bot.sh" << 'EOF'
#!/bin/bash
echo "STATUS: BronxBot Status:"
systemctl --user status bronxbot --no-pager -l
EOF

# Logs script
cat > "$SCRIPT_DIR/logs_bot.sh" << 'EOF'
#!/bin/bash
echo "LOGS: BronxBot Logs (last 50 lines):"
journalctl --user -u bronxbot -n 50 --no-pager
echo ""
echo "FILES: Recent log files:"
ls -la logs/bronxbot_*.log 2>/dev/null | tail -5 || echo "No log files found"
EOF

# Tray script
cat > "$SCRIPT_DIR/start_tray.sh" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
$VENV_PATH/bin/python $SCRIPT_DIR/bronxbot_tray.py &
echo "TRAY: System tray started"
EOF

# Make all scripts executable
chmod +x "$SCRIPT_DIR"/*.sh

echo "SUCCESS: Convenience scripts created"

echo ""
echo "Setup Complete!"
echo "==============="
echo ""
echo "Available commands:"
echo "  ./start_bot.sh     - Start the bot service"
echo "  ./stop_bot.sh      - Stop the bot service" 
echo "  ./status_bot.sh    - Check bot status"
echo "  ./logs_bot.sh      - View bot logs"
echo "  ./start_tray.sh    - Start system tray manually"
echo ""
echo "The bot will now:"
echo "  ✅ Start automatically on boot"
echo "  ✅ Run silently in the background"  
echo "  ✅ Show a system tray icon (after reboot or manual start)"
echo "  ✅ Restart automatically if it crashes"
echo ""
echo "To start everything now:"
echo "  1. ./start_bot.sh"
echo "  2. ./start_tray.sh"
echo ""
echo "Or just reboot your system for full auto-start!"
