#!/bin/bash

# Development Testing Script
# Run this to test the application locally without installing

echo "WLED Manager - Development Mode"
echo "================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Set environment variables
export WLED_MANAGER_CONFIG="config/config.yaml"

# Run the application
echo ""
echo "Starting WLED Manager..."
echo "Access the web interface at: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 src/app.py
