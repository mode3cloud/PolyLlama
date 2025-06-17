# MCP (Model Context Protocol) Integration

This document explains how to configure and use MCP tools with PolyLlama.

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

## Troubleshooting

1. **MCP tools not loading**: Check the container logs for MCP initialization errors
2. **Tool execution fails**: Verify the MCP server is properly configured and has required permissions
3. **Missing dependencies**: Run `pnpm install` to ensure MCP SDK is installed