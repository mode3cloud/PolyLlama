#!/bin/bash

# Start both the main LLM proxy service and the MCP server

echo "Starting PolyLlama LLM Proxy services..."

# Start the MCP server on port 3001 in the background
echo "Starting MCP Server on port 3001..."
.venv/bin/python mcp_server_app.py &
MCP_PID=$!

# Start the main LLM proxy service on port 11435
echo "Starting LLM Proxy on port 11435..."
.venv/bin/python main.py &
MAIN_PID=$!

# Function to handle shutdown
shutdown() {
    echo "Shutting down services..."
    kill $MCP_PID $MAIN_PID 2>/dev/null
    wait $MCP_PID $MAIN_PID 2>/dev/null
    echo "Services stopped."
    exit 0
}

# Set up signal handlers
trap shutdown SIGTERM SIGINT

# Wait for both processes
wait $MCP_PID $MAIN_PID