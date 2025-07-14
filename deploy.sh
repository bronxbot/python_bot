#!/bin/bash
# Deploy BronxBot to production

set -e

echo "Deploying BronxBot to production..."

# Configuration
SERVICE_NAME="bronxbot"
USER="bronxbot"
DEPLOY_DIR="/home/$USER/bronx-rewritten"
BACKUP_DIR="/home/$USER/backups"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root"
    exit 1
fi

# Create user if it doesn't exist
if ! id "$USER" &>/dev/null; then
    echo "Creating user: $USER"
    useradd -m -s /bin/bash "$USER"
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"
chown "$USER:$USER" "$BACKUP_DIR"

# Stop existing service if running
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Stopping existing service..."
    systemctl stop "$SERVICE_NAME"
fi

# Backup existing installation
if [ -d "$DEPLOY_DIR" ]; then
    echo "Backing up existing installation..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    tar -czf "$BACKUP_DIR/bronxbot_backup_$timestamp.tar.gz" -C "$DEPLOY_DIR" .
    echo "Backup created: $BACKUP_DIR/bronxbot_backup_$timestamp.tar.gz"
fi

# Create deploy directory
mkdir -p "$DEPLOY_DIR"
chown "$USER:$USER" "$DEPLOY_DIR"

# Copy files
echo "Copying files..."
cp -r . "$DEPLOY_DIR/"
chown -R "$USER:$USER" "$DEPLOY_DIR"

# Install Python dependencies
echo "Installing Python dependencies..."
sudo -u "$USER" bash -c "cd $DEPLOY_DIR && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"

# Install systemd service
echo "Installing systemd service..."
cp "$DEPLOY_DIR/bronxbot.service" "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# Create log directory
mkdir -p "$DEPLOY_DIR/logs"
chown "$USER:$USER" "$DEPLOY_DIR/logs"

# Set up log rotation
cat > "/etc/logrotate.d/bronxbot" << EOF
$DEPLOY_DIR/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    su $USER $USER
}
EOF

# Create environment file from template if it doesn't exist
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    echo "Creating environment file..."
    cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
    chown "$USER:$USER" "$DEPLOY_DIR/.env"
    chmod 600 "$DEPLOY_DIR/.env"
    echo "Please edit $DEPLOY_DIR/.env with your configuration"
fi

# Start service
echo "Starting service..."
systemctl start "$SERVICE_NAME"

# Check status
sleep 3
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "BronxBot deployed and started successfully!"
    echo "Status: systemctl status $SERVICE_NAME"
    echo "Logs: journalctl -u $SERVICE_NAME -f"
else
    echo "Service failed to start. Check logs: journalctl -u $SERVICE_NAME"
    exit 1
fi

echo ""
echo "Deployment complete!"
echo "Next steps:"
echo "1. Edit $DEPLOY_DIR/.env with your configuration"
echo "2. Restart the service: systemctl restart $SERVICE_NAME"
echo "3. Monitor logs: journalctl -u $SERVICE_NAME -f"
