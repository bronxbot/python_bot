#!/bin/bash
echo "STATUS: BronxBot Services Status:"
echo ""
echo "=== Bot Service ==="
systemctl --user status bronxbot --no-pager -l
echo ""
echo "=== Tray Service ==="
systemctl --user status bronxbot-tray --no-pager -l
