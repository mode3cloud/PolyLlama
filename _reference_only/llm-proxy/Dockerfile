FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY services/llm-proxy/pyproject.toml ./
RUN pip install uv && uv pip install --system \
    fastapi>=0.104.0 \
    "uvicorn[standard]>=0.24.0" \
    pydantic>=2.0.0 \
    httpx>=0.25.0 \
    "litellm>=1.30.0" \
    neo4j>=5.0.0 \
    python-multipart>=0.0.6 \
    aiofiles>=23.0.0 \
    python-magic>=0.4.27 \
    faster-whisper>=0.10.0 \
    speechrecognition>=3.10.0 \
    pydub>=0.25.0

# Copy source code
COPY services/llm-proxy/ .

# Copy shared services from mcp_tools directory for imports
COPY services/mcp_tools /app/mcp_tools

# Create uploads directory
RUN mkdir -p /tmp/llm-proxy-uploads

# Expose LLM proxy service port
EXPOSE 11435

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:11435/health || exit 1

# Run the LLM Proxy service
CMD ["python", "main.py"]