#!/bin/bash

# Start script for Medical Entity Extraction API

set -e

echo "Starting Medical Entity Extraction API..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Please edit .env and add your OPENAI_API_KEY"
        exit 1
    fi
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Run with uvicorn (development)
if [ "$1" = "dev" ]; then
    echo "Starting development server with uvicorn..."
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
# Run with gunicorn (production)
else
    echo "Starting production server with gunicorn..."
    gunicorn app:app -c gunicorn_config.py
fi
