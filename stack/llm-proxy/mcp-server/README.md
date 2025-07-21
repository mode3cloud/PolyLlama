# PolyLlama MCP Server

This service exposes PolyLlama's orchestration capabilities as an MCP (Model Context Protocol) server that external applications can consume.

## Overview

The PolyLlama MCP Server allows external applications like Claude Desktop, IDEs, and other MCP-compatible tools to discover and use PolyLlama's native capabilities as tools. This includes model management, instance routing, system status, and GPU metrics.

## Available Tools

The server exposes the following PolyLlama tools via MCP:

| Tool Name | Description |
|-----------|-------------|
| `polyllama_list_models` | List all available models across PolyLlama instances |
| `polyllama_load_model` | Load a model on the optimal PolyLlama instance |
| `polyllama_get_status` | Get PolyLlama system status and health information |
| `polyllama_get_running_models` | Get currently running models across all instances |
| `polyllama_route_request` | Execute a direct Ollama API request with PolyLlama routing |
| `polyllama_get_model_mappings` | Get current model-to-instance mappings and routing information |

## Usage

### Connecting from Claude Desktop

Add this configuration to your Claude Desktop MCP settings:

```json
{
  "mcpServers": {
    "polyllama": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sse"],
      "env": {
        "SSE_URL": "http://localhost:3001/sse"
      }
    }
  }
}
```

### Connecting from Other MCP Clients

Use the SSE transport to connect to:
- **Endpoint**: `http://localhost:3001/sse`
- **Protocol**: MCP over Server-Sent Events (SSE)
- **Authentication**: API key required if `POLYLLAMA_API_KEY` is set

### Direct HTTP Endpoints

The server also provides REST endpoints for inspection:

- `GET http://localhost:3001/info` - Server information and available tools
- `GET http://localhost:3001/health` - Health check endpoint

## Configuration

The MCP server is configured through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_SERVER_PORT` | Port for the MCP server | 3001 |
| `OLLAMA_BASE_URL` | PolyLlama base URL | `http://polyllama:11434` |
| `POLYLLAMA_API_KEY` | API key for authentication | (optional) |

## Examples

### Using PolyLlama Tools in Claude Desktop

Once connected, you can use PolyLlama tools in your conversations:

```
User: Can you list all available models in my PolyLlama setup?

Claude: I'll check what models are available in your PolyLlama instance.

[Tool: polyllama_list_models]
Available models in PolyLlama:
{
  "models": [
    {"name": "llama3.2:3b", "size": 2.0, "modified_at": "2024-01-15T10:30:00Z"},
    {"name": "codellama:7b", "size": 3.8, "modified_at": "2024-01-14T15:22:00Z"}
  ]
}

You have 2 models available: llama3.2:3b (2.0GB) and codellama:7b (3.8GB).
```

```
User: Load the codellama model for me

Claude: I'll load the codellama:7b model on the optimal PolyLlama instance.

[Tool: polyllama_load_model]
{"name": "codellama:7b"}

Model loading initiated: codellama:7b
The model is now being loaded on the best available instance.
```

### Checking System Status

```
User: What's the current status of my PolyLlama system?

Claude: Let me check the current status of your PolyLlama system.

[Tool: polyllama_get_status]
{"include_metrics": true}

PolyLlama System Status:
{
  "instances": {
    "polyllama1": {"status": "online", "gpu": "RTX 4090"},
    "polyllama2": {"status": "online", "gpu": "RTX 4090"}
  },
  "modelMappings": {
    "llama3.2:3b": "polyllama1",
    "codellama:7b": "polyllama2"
  },
  "metrics": {
    "gpu_usage": [45, 67],
    "memory_usage": [8.2, 12.1]
  }
}

Your PolyLlama system is healthy with 2 online instances, each with RTX 4090 GPUs.
```

## Development

### Running Locally

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev

# Run tests (if available)
npm test
```

### Building

The service is automatically built as part of the PolyLlama stack:

```bash
# Rebuild the entire stack
./polyllama.sh --build

# Or just rebuild the MCP server
docker build -t polyllama-mcp-server stack/llm-proxy/mcp-server/
```

## Architecture

```
External MCP Client (Claude Desktop, IDEs, etc.)
           ↓ (SSE Connection)
    Nginx Router (:11434/sse)
           ↓ (Proxy)
    MCP Server (:3001/sse)
           ↓ (HTTP Calls)
    PolyLlama Router (:11434/api/*)
           ↓ (Lua Routing)
    Ollama Instances (polyllama1, polyllama2, etc.)
```

The MCP server acts as a bridge, exposing PolyLlama's capabilities through the standardized MCP protocol while maintaining all existing security and routing logic.

## Security

- **API Key Protection**: If `POLYLLAMA_API_KEY` is configured, all requests to PolyLlama endpoints are automatically authenticated
- **CORS**: Configured to allow connections from authorized domains
- **Isolation**: The MCP server runs in its own container with minimal privileges
- **Input Validation**: All tool arguments are validated before execution

## Troubleshooting

### Connection Issues

1. Verify MCP server is running: `curl http://localhost:3001/health`
2. Check MCP server logs: `docker logs mcp-server`
3. Test SSE endpoint: `curl -H "Accept: text/event-stream" http://localhost:3001/sse`

### Authentication Issues

1. Verify API key is set correctly in environment
2. Check that the same API key is used by both client and server
3. Review authentication logs in the MCP server container

### Tool Execution Failures

1. Check if target models/instances are available
2. Verify network connectivity between services
3. Review tool-specific error messages in the response

## Support

For issues specific to the MCP server implementation, check:
- Container logs: `docker logs mcp-server`
- PolyLlama router status: `http://localhost:11434/api/polyllama/instance-status`
- MCP server health: `http://localhost:3001/health`