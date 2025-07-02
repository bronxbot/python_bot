#!/bin/bash
if pgrep -f "bronxbot_tray.py" > /dev/null; then
    pkill -f "bronxbot_tray.py"
    echo "TRAY: System tray stopped"
else
    echo "TRAY: Not running"
fi
