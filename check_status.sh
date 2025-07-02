#!/bin/bash
# Test if the tray is running

echo "🔍 Checking system tray status..."

# Check if tray process is running
if pgrep -f "bronxbot_tray.py" > /dev/null; then
    echo "✅ System tray is running (PID: $(pgrep -f bronxbot_tray.py))"
else
    echo "❌ System tray is not running"
fi

# Check if bot service is running
if systemctl --user is-active --quiet bronxbot; then
    echo "✅ Bot service is active"
    echo "📊 Service status:"
    systemctl --user status bronxbot --no-pager -l | head -3
else
    echo "❌ Bot service is not active"
fi

echo ""
echo "🖥️  To start the tray manually: ./start_tray.sh"
echo "🤖 To check bot logs: ./logs_bot.sh"
