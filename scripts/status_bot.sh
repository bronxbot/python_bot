#!/bin/bash
echo "STATUS: BronxBot Service Status:"
echo ""
echo "=== Bot Service ==="
systemctl --user status bronxbot --no-pager -l
echo ""
echo "=== Tray Process ==="
if pgrep -f "bronxbot_tray.py" > /dev/null; then
    echo "Tray is running (PID: $(pgrep -f bronxbot_tray.py))"
else
    echo "Tray is not running"
fi
