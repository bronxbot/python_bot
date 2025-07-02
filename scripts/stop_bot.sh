#!/bin/bash
echo "Stopping BronxBot services..."
systemctl --user stop bronxbot-tray
systemctl --user stop bronxbot
echo "STOPPED: BronxBot and tray stopped"
