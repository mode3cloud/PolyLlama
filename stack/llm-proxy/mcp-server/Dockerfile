FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Node.js for npx-based MCP servers
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    gnupg \
    lsof \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for SSE/HTTP transport
EXPOSE 3001

# Default to SSE transport for compatibility with n8n and MCP Inspector
ENV MCP_TRANSPORT=sse

# Run the server
CMD ["sh", "-c", "python server.py --transport ${MCP_TRANSPORT:-sse}"]