#!/bin/bash

echo "=== MCP Bridge Startup ==="
echo "Starting MCP package installation..."

# Install MCP packages at runtime (non-blocking, in background)
{
    echo "Installing MCP server packages..."

    # Install packages one by one to avoid failures stopping the entire process
    npm install -g @modelcontextprotocol/server-github 2>/dev/null || echo "Failed: github"
    npm install -g @modelcontextprotocol/server-sequential-thinking 2>/dev/null || echo "Failed: sequential-thinking"
    npm install -g @upstash/context7-mcp 2>/dev/null || echo "Failed: context7"
    npm install -g @browsermcp/mcp@latest 2>/dev/null || echo "Failed: browsermcp"
    npm install -g firecrawl-mcp 2>/dev/null || echo "Failed: firecrawl"
    npm install -g @hubspot/mcp-server 2>/dev/null || echo "Failed: hubspot"
    npm install -g @tiberriver256/mcp-server-azure-devops 2>/dev/null || echo "Failed: azure-devops"
    npm install -g mcp-remote@latest 2>/dev/null || echo "Failed: mcp-remote"
    npm install -g n8n-mcp 2>/dev/null || echo "Failed: n8n-mcp"

    # Touch a file to indicate installation is complete
    touch /app/mcp-packages-installed.flag
    echo "MCP package installation completed."
} &

# Start the Python MCP bridge server immediately
echo "Starting MCP Bridge server..."
exec python -u mcp_bridge_server.py