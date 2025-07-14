#!/bin/bash
# Check BronxBot status

echo "Checking BronxBot status..."

# Check if bot process is running
if pgrep -f "python main.py" > /dev/null; then
    echo "BronxBot is running"
    
    # Get process info
    pid=$(pgrep -f "python main.py")
    echo "Process ID: $pid"
    
    # Get memory usage
    memory=$(ps -p $pid -o rss --no-headers)
    echo "Memory usage: $((memory / 1024)) MB"
    
    # Check uptime
    start_time=$(ps -p $pid -o lstart --no-headers)
    echo "Started: $start_time"
else
    echo "BronxBot is not running"
fi

# Check log files
echo ""
echo "Recent log files:"
ls -la logs/ | tail -5

# Check if MongoDB is accessible (if configured)
if command -v mongosh &> /dev/null; then
    echo ""
    echo "Checking MongoDB connection..."
    timeout 5 mongosh --eval "db.runCommand('ping')" &> /dev/null
    if [ $? -eq 0 ]; then
        echo "MongoDB is accessible"
    else
        echo "MongoDB connection failed"
    fi
fi
