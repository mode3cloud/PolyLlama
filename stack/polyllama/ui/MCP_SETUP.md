# MCP (Model Context Protocol) Integration

This document explains how to configure and use MCP tools with PolyLlama.

PolyLlama supports MCP in two ways:
1. **MCP Client** - Consume tools from external MCP servers
2. **MCP Server** - Expose PolyLlama's capabilities as MCP tools for external applications

## Configuration

1. Copy the example configuration:
   ```bash
   cp stack/polyllama/ui/mcp-config.example.json mcp-config.json
   ```

2. Edit `mcp-config.json` to add your MCP servers. Example:
   ```json
   {
     "mcpServers": {
       "filesystem": {
         "command": "npx",
         "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/docs"],
         "env": {}
       },
       "github": {
         "command": "npx",
         "args": ["-y", "@modelcontextprotocol/server-github"],
         "env": {
           "GITHUB_TOKEN": "your-github-token"
         }
       }
     }
   }
   ```

3. The configuration file is automatically mounted into the Docker container at `/app/mcp-config.json`.

## Usage

### In the Chat Interface

When sending a chat request, include `enableMCPTools: true` in your request to automatically include all available MCP tools:

```javascript
const response = await fetch('/ui/api/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'claude-3-5-sonnet',
    messages: [...],
    enableMCPTools: true  // This enables MCP tools
  })
})
```

### API Endpoints

- `GET /ui/api/mcp/tools` - List all available MCP tools
- `POST /ui/api/mcp/tools` - Execute a specific MCP tool

Example tool execution:
```javascript
const result = await fetch('/ui/api/mcp/tools', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    tool_name: 'read_file',
    arguments: {
      path: '/path/to/file.txt'
    }
  })
})
```

## Supported MCP Servers

Common MCP servers you can use:
- `@modelcontextprotocol/server-filesystem` - File system access
- `@modelcontextprotocol/server-github` - GitHub API access
- `@modelcontextprotocol/server-postgres` - PostgreSQL database access
- `@modelcontextprotocol/server-sqlite` - SQLite database access
- `@modelcontextprotocol/server-playwright` - Web automation
- `@modelcontextprotocol/server-puppeteer` - Web scraping

## Security Notes

- The `mcp-config.json` file is excluded from git as it may contain sensitive API keys
- MCP servers run with the same permissions as the UI container
- Always review MCP server documentation for security implications

## PolyLlama as an MCP Server

PolyLlama exposes its own capabilities as an MCP server that external applications can consume.

### Connecting to PolyLlama from Claude Desktop

Add this configuration to your Claude Desktop MCP settings (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

**If API Key is Required**: When `POLYLLAMA_API_KEY` is set, add authentication:

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

### Available Tools via PolyLlama MCP Server

When connected as an MCP server, PolyLlama exposes **all configured MCP tools** from your `mcp-config.json`. This includes:

**Filesystem Tools** (if configured):
- `filesystem__read_file` - Read file contents
- `filesystem__write_file` - Write files
- `filesystem__list_directory` - List directory contents

**GitHub Tools** (if configured):
- `github__search_repositories` - Search repositories
- `github__get_file` - Get file contents from repos
- `github__create_issue` - Create issues

**Database Tools** (if configured):
- `postgres__query` - Execute PostgreSQL queries
- `sqlite__execute` - Execute SQLite commands

**And any other tools** you've configured in your MCP setup. The exact list depends on your `mcp-config.json` configuration.

### MCP Server Endpoints

- **MCP Endpoint**: `http://localhost:11434/mcp` - Main MCP protocol endpoint (supports both SSE and HTTP streamable transport)
- **Info Endpoint**: `http://localhost:11434/mcp-server/info` - Server capabilities (protected)
- **Health Endpoint**: `http://localhost:11434/mcp-server/health` - Health check (protected)

**Authentication**: All endpoints require the same API key as other PolyLlama APIs when `POLYLLAMA_API_KEY` is configured.

### Example Usage in Claude Desktop

Once connected, you can use PolyLlama tools directly in conversations:

```
User: What models are available in my PolyLlama setup?

Claude: [Uses polyllama_list_models tool]
I can see you have llama3.2:3b and codellama:7b available...

User: Load the codellama model please

Claude: [Uses polyllama_load_model tool]
I'll load codellama:7b on the optimal instance for you...
```

## Troubleshooting

### MCP Client (Consuming External Tools)
1. **MCP tools not loading**: Check the container logs for MCP initialization errors
2. **Tool execution fails**: Verify the MCP server is properly configured and has required permissions
3. **Missing dependencies**: Run `pnpm install` to ensure MCP SDK is installed

### MCP Server (PolyLlama as Server)
1. **Connection issues**: Verify PolyLlama is running and accessible at `http://localhost:11434`
2. **MCP endpoint not working**: Check `http://localhost:11434/mcp-server/health` (with API key if required)
3. **Tool execution fails**: Review logs with `docker logs mcp-server`
4. **Authentication issues**: Ensure API key is correctly configured if using `POLYLLAMA_API_KEY`
   - Test with: `curl -H "api-key: your_key" -H "Accept: text/event-stream" http://localhost:11434/mcp`
   - Verify the key matches your `.env` file setting