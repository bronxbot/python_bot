#!/bin/bash
echo "Restarting BronxBot services..."
systemctl --user restart bronxbot
systemctl --user restart bronxbot-tray
echo "SUCCESS: BronxBot and tray restarted"
echo ""
echo "Bot status:"
systemctl --user status bronxbot --no-pager -l
echo ""
echo "Tray status:"
systemctl --user status bronxbot-tray --no-pager -l
