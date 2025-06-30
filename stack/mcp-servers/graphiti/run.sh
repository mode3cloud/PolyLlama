#!/bin/bash
# Graphiti MCP Server Runner
#
# This script sets up and runs the Graphiti MCP server

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the server directory
cd "$SCRIPT_DIR"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in PATH" >&2
    exit 1
fi

# Install dependencies if requirements.txt exists and packages aren't installed
if [ -f "requirements.txt" ]; then
    # Check if MCP is installed
    if ! python3 -c "import mcp" &> /dev/null; then
        echo "Installing dependencies..."
        python3 -m pip install -r requirements.txt
    fi
fi

# Make server.py executable
chmod +x server.py

# Run the server
echo "Starting Graphiti MCP Server..." >&2
exec python3 server.py