#!/bin/bash

# Setup script for Face Detection API

echo "Setting up Face Detection API..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp env.example .env
    echo "Please edit .env file with your AWS credentials before running the application."
fi

echo "Setup complete!"
echo "To start the application:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Edit .env file with your AWS credentials"
echo "3. Run: python run.py"