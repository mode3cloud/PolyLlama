#!/bin/bash

# Restart LLM Proxy and Router services
# This script stops and restarts the llm-proxy and router services

set -e

echo "🔄 Restarting LLM Proxy and Router services..."

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if docker compose file exists
if [ ! -f "$SCRIPT_DIR/builder/built/docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found at $SCRIPT_DIR/builder/built/"
    echo "Please run ./polyllama.sh first to generate the configuration."
    exit 1
fi

# Stop the services
echo "⏹️  Stopping llm-proxy and router services..."
docker compose -f "$SCRIPT_DIR/builder/built/docker-compose.yml" stop llm-proxy router

# Rebuild and start the services
echo "🔨 Rebuilding and starting llm-proxy and router services..."
docker compose -f "$SCRIPT_DIR/builder/built/docker-compose.yml" up -d --build llm-proxy router

# Wait a moment for services to start
sleep 2

# Check if services are running
echo "✅ Checking service status..."
docker compose -f "$SCRIPT_DIR/builder/built/docker-compose.yml" ps llm-proxy router

echo "🎉 Services restarted successfully!"
