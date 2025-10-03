FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y \
    git \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Create directory for npm packages
RUN mkdir -p /app/mcp-packages

# Set npm prefix for global packages to a writable directory
ENV NPM_CONFIG_PREFIX=/app/mcp-packages
ENV PATH="/app/mcp-packages/bin:${PATH}"

# Copy requirements and install Python dependencies
COPY stack/mcp-bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP bridge implementation
COPY stack/mcp-bridge/mcp_bridge_server.py .
COPY stack/mcp-bridge/startup.sh .
COPY stack/llm-proxy/services/mcp_manager.py ./services/
COPY stack/llm-proxy/services/mcp_connector.py ./services/
COPY stack/llm-proxy/services/mcp_discovery.py ./services/
COPY stack/llm-proxy/services/mcp_proxy_client.py ./services/
COPY stack/llm-proxy/services/fastmcp_dual_transport_patch.py ./services/
COPY stack/llm-proxy/mcp_server_fastmcp.py .

# Make startup script executable
RUN chmod +x /app/startup.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_CONFIG_PATH=/app/mcp-config.json
ENV MCP_SERVER_PORT=3001

EXPOSE 3001

# Run the startup script which installs packages and starts the server
CMD ["/app/startup.sh"]