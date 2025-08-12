#!/bin/bash

# Test: Start only the MCP server to isolate the issue

echo "Starting PolyLlama MCP Server (FastMCP test)..."

# Start the MCP server on port 3001 as main process
echo "Starting MCP Server (FastMCP with dual transport) on port 3001..."
.venv/bin/python mcp_server_fastmcp.py --transport dual