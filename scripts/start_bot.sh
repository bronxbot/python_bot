#!/bin/bash
echo "Starting BronxBot service..."
systemctl --user start bronxbot
echo "SUCCESS: BronxBot started"
echo ""
echo "Bot status:"
systemctl --user status bronxbot --no-pager -l
