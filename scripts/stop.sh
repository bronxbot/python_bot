#!/bin/bash
# Stop BronxBot

echo "Stopping BronxBot..."

# Find and kill the bot process
if pgrep -f "python main.py" > /dev/null; then
    pid=$(pgrep -f "python main.py")
    echo "Found BronxBot process: $pid"
    
    # Send SIGTERM first (graceful shutdown)
    echo "Sending SIGTERM..."
    kill -TERM $pid
    
    # Wait for graceful shutdown
    sleep 5
    
    # Check if process is still running
    if pgrep -f "python main.py" > /dev/null; then
        echo "Process still running, sending SIGKILL..."
        kill -KILL $pid
        sleep 2
    fi
    
    # Final check
    if pgrep -f "python main.py" > /dev/null; then
        echo "Failed to stop BronxBot"
        exit 1
    else
        echo "BronxBot stopped successfully"
    fi
else
    echo "BronxBot is not running"
fi
