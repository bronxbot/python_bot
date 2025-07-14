#!/bin/bash
# Setup script for BronxBot

echo "Setting up BronxBot..."

# Check if Python 3.8+ is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please edit .env file with your bot token and database credentials"
fi

# Create data directories if they don't exist
echo "Creating data directories..."
mkdir -p logs
mkdir -p data/backups

# Set executable permissions on scripts
chmod +x scripts/*.sh

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your bot token and database credentials"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python main.py"
echo ""
echo "Or use the management scripts in the scripts/ directory"
