#!/bin/bash

# QR Print Client Installation Script for Linux/macOS
# This script sets up a virtual environment and runs the print client

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_SCRIPT="$SCRIPT_DIR/gui_qr_print_service.py"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

echo "========================================="
echo "QR Print Client Installation & Launcher"
echo "========================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "Error: Python is not installed or not in PATH"
        echo "Please install Python 3.8+ and try again"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

echo "Using Python: $PYTHON_CMD"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment found"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install/upgrade pip
echo "Updating pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install requirements
if [ -f "$REQUIREMENTS" ]; then
    echo "Installing requirements..."
    pip install -r "$REQUIREMENTS" > /dev/null 2>&1
    echo "✓ Requirements installed"
else
    echo "Installing requests library..."
    pip install requests > /dev/null 2>&1
    echo "✓ Dependencies installed"
fi

# Check if the Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: gui_qr_print_service.py not found!"
    exit 1
fi

echo "✓ Setup complete!"
echo ""
echo "Starting QR Print Client..."
echo "========================================="

# Run the application
python "$PYTHON_SCRIPT"

echo ""
echo "QR Print Client has been closed."
echo ""
echo "To run again, execute: ./install.sh"
echo "Or activate the environment and run: python gui_qr_print_service.py"