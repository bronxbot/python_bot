#!/bin/bash
echo "Restarting BronxBot service..."
systemctl --user restart bronxbot
echo "SUCCESS: BronxBot restarted"
echo ""
echo "Bot status:"
systemctl --user status bronxbot --no-pager -l
