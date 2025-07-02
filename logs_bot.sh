#!/bin/bash
echo "BronxBot Logs (last 50 lines):"
journalctl --user -u bronxbot -n 50 --no-pager
echo ""
echo "Recent log files:"
ls -la logs/bronxbot_*.log 2>/dev/null | tail -5 || echo "No log files found"
