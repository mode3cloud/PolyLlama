#!/bin/bash

# Start Ollama in the background on port 11434
echo "Starting Ollama service on port 11434..."
OLLAMA_HOST=0.0.0.0:11434 /bin/ollama serve 2>&1 | grep -v '\[GIN\]'