FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Node.js 20
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml from root for dependency installation
COPY pyproject.toml uv.lock* ./

# Install uv and dependencies in one step
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    export PATH="/root/.local/bin:$PATH" && \
    /root/.local/bin/uv venv && \
    . .venv/bin/activate && \
    /root/.local/bin/uv pip install -e .

# Set PATH for subsequent commands
ENV PATH="/root/.local/bin:$PATH"

# Copy application code
COPY stack/llm-proxy/ .

# Expose port
EXPOSE 11435

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:11435/health || exit 1

# Run the application
CMD [".venv/bin/python", "main.py"]