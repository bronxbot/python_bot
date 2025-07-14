#!/bin/bash
# Restart BronxBot

echo "Restarting BronxBot..."

# Stop the bot first
./scripts/stop.sh

# Wait a moment
sleep 2

# Start the bot
./scripts/start.sh
