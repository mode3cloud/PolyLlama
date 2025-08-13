#!/bin/bash
set -e

echo "Starting PolyLlama LLM Proxy Service..."

# Set environment variable to use MCP proxy client
export USE_MCP_PROXY=true

# Start the MCP server in the background on port 3001
echo "Starting MCP Server (FastMCP with dual transport) on port 3001..."
.venv/bin/python mcp_server_fastmcp.py --transport dual &
MCP_SERVER_PID=$!

# Give MCP server a moment to start
sleep 10

# Start the main LLM proxy service on port 11435
echo "Starting LLM Proxy Service on port 11435..."
.venv/bin/python main.py

# If main service exits, clean up MCP server
echo "Stopping MCP server..."
kill $MCP_SERVER_PID 2>/dev/null || true