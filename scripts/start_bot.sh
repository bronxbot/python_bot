#!/bin/bash
systemctl --user start bronxbot
echo "SUCCESS: BronxBot started"
systemctl --user status bronxbot --no-pager -l
