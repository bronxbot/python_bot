#!/bin/bash
systemctl --user start bronxbot
echo "BronxBot started"
systemctl --user status bronxbot --no-pager -l
