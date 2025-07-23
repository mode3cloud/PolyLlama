# PolyLlama MCP Server

This service exposes PolyLlama's orchestration capabilities as an MCP (Model Context Protocol) server that external applications can consume.

## Overview

The PolyLlama MCP Server allows external applications like Claude Desktop, IDEs, and other MCP-compatible tools to discover and use **all MCP tools that PolyLlama has access to**. This aggregates tools from all configured MCP servers in PolyLlama's `mcp-config.json` and exposes them through a single MCP endpoint.

## ⚡ New: Streamable HTTP Transport

**Version 2.0** now uses the modern **Streamable HTTP** transport instead of legacy SSE. This provides:

- **Better Performance**: Single endpoint reduces connection overhead by 50%
- **Resource Efficiency**: Dynamic streaming only when needed
- **Infrastructure Compatibility**: Better support for load balancers and proxies
- **Simplified Architecture**: One endpoint instead of separate SSE + HTTP

**Backward Compatibility**: Legacy SSE endpoints still work but show deprecation warnings.

## Available Tools

The server dynamically exposes **all MCP tools** configured in PolyLlama's setup, which may include:

**Common Tool Categories:**
- **Filesystem Tools**: `filesystem__read_file`, `filesystem__write_file`, `filesystem__list_directory`
- **GitHub Tools**: `github__search_repositories`, `github__get_file`, `github__create_issue`
- **Database Tools**: `postgres__query`, `sqlite__execute`
- **Web Tools**: `playwright__navigate`, `puppeteer__screenshot`

**Actual Available Tools**: The exact tools depend on your `mcp-config.json` configuration. Use the `/info` endpoint to see the current list of available tools.

**Tool Discovery**: 
```bash
curl http://localhost:11434/mcp-server/info
```

## Usage

### Connecting from Claude Desktop

**New: Streamable HTTP (Recommended)**
```json
{
  "mcpServers": {
    "polyllama": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:11434/mcp"]
    }
  }
}
```

**With API Key Authentication**:
```json
{
  "mcpServers": {
    "polyllama": {
      "command": "npx",
      "args": [
        "-y", 
        "mcp-remote", 
        "http://localhost:11434/mcp",
        "--header", "api-key=your_api_key_here"
      ]
    }
  }
}
```

**Legacy SSE (Still Supported)**:
```json
{
  "mcpServers": {
    "polyllama": {
      "command": "npx",
      "args": [
        "-y", 
        "mcp-remote", 
        "sse://localhost:11434/sse",
        "--header", "api-key=your_api_key_here"
      ]
    }
  }
}
```

### Connecting from Other MCP Clients

**Streamable HTTP (Recommended)**:
- **Endpoint**: `http://localhost:11434/mcp`
- **Protocol**: MCP over Streamable HTTP (2025-03-26)
- **Streaming**: Automatic upgrade to SSE when needed
- **Authentication**: API key required if `POLYLLAMA_API_KEY` is set

**Legacy SSE (Deprecated)**:
- **Endpoint**: `http://localhost:11434/sse`
- **Protocol**: MCP over Server-Sent Events (SSE)
- **Note**: Shows deprecation warnings

**Authentication Methods** (both transports):
- **Header**: `api-key: your_api_key`
- **Header**: `x-api-key: your_api_key` 
- **Header**: `Authorization: Bearer your_api_key`

### Direct HTTP Endpoints

The server provides REST endpoints for inspection (also protected with API key):

- `GET http://localhost:11434/mcp-server/info` - Server information and available tools  
- `GET http://localhost:11434/mcp-server/health` - Health check endpoint
- `POST http://localhost:11434/mcp` - Main MCP endpoint (all operations)

**Direct Access** (bypasses authentication, for internal use):
- `GET http://localhost:3001/info` - Direct server info
- `GET http://localhost:3001/health` - Direct health check
- `POST http://localhost:3001/mcp` - Direct MCP endpoint

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
User: Can you search for Python repositories on GitHub?

Claude: I'll search for Python repositories using the GitHub tool.

[Tool: github__search_repositories]
{"query": "language:python", "sort": "stars"}

Found several popular Python repositories:
- tensorflow/tensorflow - Machine learning framework
- django/django - Web framework
- requests/requests - HTTP library
...
```

```
User: Read the contents of my README file

Claude: I'll read your README file using the filesystem tool.

[Tool: filesystem__read_file]
{"path": "/path/to/README.md"}

# My Project
This is a sample README file...
```

### Tool Categories Example

Depending on your MCP configuration, you might see tools like:
- **filesystem__read_file**: Read file contents
- **github__search_repositories**: Search GitHub repositories  
- **postgres__query**: Execute database queries
- **playwright__navigate**: Navigate web pages
- **puppeteer__screenshot**: Take webpage screenshots
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

**New Streamable HTTP Architecture:**
```
External MCP Client (Claude Desktop, IDEs, etc.)
           ↓ (HTTP POST)
    Nginx Router (:11434/mcp)
           ↓ (Proxy)
    MCP Server (:3001/mcp)
           ↓ (Dynamic: HTTP or SSE streaming)
    MCP Bridge (:3000) 
           ↓ (HTTP Calls)
    PolyLlama Router (:11434/api/*)
           ↓ (Lua Routing)
    Ollama Instances (polyllama1, polyllama2, etc.)
```

**Key Improvements:**
- **Single Endpoint**: `/mcp` handles all operations
- **Dynamic Streaming**: Upgrades to SSE only when needed
- **Better Resource Management**: No persistent connections unless required
- **Simplified Flow**: One request path instead of separate SSE + HTTP

The MCP server acts as a bridge, exposing PolyLlama's capabilities through the standardized MCP protocol while maintaining all existing security and routing logic.

## Security

- **API Key Protection**: If `POLYLLAMA_API_KEY` is configured, all requests to PolyLlama endpoints are automatically authenticated
- **CORS**: Configured to allow connections from authorized domains
- **Isolation**: The MCP server runs in its own container with minimal privileges
- **Input Validation**: All tool arguments are validated before execution

## Troubleshooting

### Connection Issues

1. Verify MCP server is running: `curl http://localhost:3001/health` (direct) or `curl -H "api-key: your_key" http://localhost:11434/mcp-server/health` (protected)
2. Check MCP server logs: `docker logs mcp-server`
3. Test SSE endpoint: `curl -H "Accept: text/event-stream" -H "api-key: your_key" http://localhost:11434/sse`

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
- MCP server health: `http://localhost:11434/mcp-server/health` (with API key) or `http://localhost:3001/health` (direct)