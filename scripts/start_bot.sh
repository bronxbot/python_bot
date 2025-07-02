#!/bin/bash
echo "Starting BronxBot services..."
systemctl --user start bronxbot
systemctl --user start bronxbot-tray
echo "SUCCESS: BronxBot and tray started"
echo ""
echo "Bot status:"
systemctl --user status bronxbot --no-pager -l
echo ""
echo "Tray status:"
systemctl --user status bronxbot-tray --no-pager -l
