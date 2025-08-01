FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
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