# MCP Server Migration: SSE to Streamable HTTP

This document outlines the migration from the legacy SSE-based MCP server to the new Streamable HTTP implementation.

## Overview

The MCP (Model Context Protocol) has evolved from using separate SSE (Server-Sent Events) endpoints to a unified Streamable HTTP approach. This change improves:

- **Resource Efficiency**: Single endpoint reduces connection overhead
- **Infrastructure Compatibility**: Better support for load balancers and proxies  
- **Connection Management**: Dynamic upgrade to streaming only when needed
- **Bidirectional Communication**: Support for server-initiated requests (future)

## Key Changes

### Architecture Differences

**Legacy SSE Approach:**
```
Client → POST /messages/?session_id=xxx (JSON-RPC request)
Client ← GET /sse (SSE stream for responses)
```

**New Streamable HTTP Approach:**
```
Client → POST /mcp (JSON-RPC request)
Client ← HTTP 200 + JSON (standard response)
         OR
Client ← HTTP 200 + text/event-stream (streaming response)
```

### Protocol Changes

| Feature | Legacy SSE | Streamable HTTP |
|---------|------------|-----------------|
| Endpoints | `/sse` + `/messages/` | `/mcp` |
| Connection Setup | Separate SSE connection required | Single request |
| Session Management | Manual session ID tracking | Request-based |
| Streaming | Always via SSE | Dynamic (HTTP or SSE) |
| Resource Usage | High (persistent connections) | Low (on-demand) |

## Implementation Details

### Server Features

The new `server_streamable_http.js` provides:

1. **Single Endpoint**: All MCP operations via `POST /mcp`
2. **Dynamic Streaming**: Upgrades to SSE only when:
   - Client sends `Accept: text/event-stream` header
   - Request is for long-running operations (tool calls)
   - Client explicitly requests streaming
3. **Backward Compatibility**: Legacy endpoints still work with deprecation warnings
4. **Improved Error Handling**: Better error reporting and connection management

### Client Integration

**Standard HTTP Request:**
```javascript
const response = await fetch('/mcp', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/list',
    params: {}
  })
});
const data = await response.json();
```

**Streaming Request:**
```javascript
const response = await fetch('/mcp', {
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream'  // Enable streaming
  },
  body: JSON.stringify({
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/call',
    params: { name: 'web_search', arguments: { query: 'test' } }
  })
});

// Handle streaming response
const reader = response.body.getReader();
// ... process SSE events
```

## Migration Steps

### 1. Update Server

```bash
# Switch to new server implementation
cd stack/llm-proxy/mcp-server
npm run start  # Uses streamable HTTP by default

# Or run legacy version
npm run start:legacy
```

### 2. Update Client Code

Replace separate SSE + HTTP calls with single `/mcp` endpoint:

```javascript
// OLD: Separate connections
const sse = new EventSource('/sse');
const response = await fetch('/messages/', { ... });

// NEW: Single endpoint
const response = await fetch('/mcp', { 
  method: 'POST',
  headers: { 'Accept': 'text/event-stream' }, // Optional for streaming
  body: JSON.stringify(mcpRequest)
});
```

### 3. Update Configuration

Update any service discovery or load balancer configs:

```yaml
# OLD endpoints
- /sse
- /messages/

# NEW endpoint
- /mcp
```

## Testing

Test the new implementation:

```bash
# Run test suite
npm test

# Or test manually
node ../../test_streamable_http.js
```

## Rollback Plan

If issues arise, revert to legacy SSE implementation:

```bash
# Use legacy server
npm run start:legacy

# Update client code to use old endpoints
# /sse and /messages/
```

## Performance Benefits

Based on MCP documentation, Streamable HTTP provides:

- **50% fewer connections** (single endpoint vs. separate SSE)
- **Reduced memory usage** (no persistent connection state)
- **Better scalability** (stateless HTTP requests)
- **Improved error recovery** (no connection state to lose)

## Compatibility

- **Backward Compatible**: Legacy endpoints remain functional
- **Protocol Version**: Supports both `2024-11-05` (SSE) and `2025-03-26` (Streamable HTTP)
- **Client Libraries**: Works with updated MCP SDK clients
- **Infrastructure**: Better support for CDNs, load balancers, and proxies

## Future Enhancements

The Streamable HTTP foundation enables:

- **Connection Resumption**: Resume interrupted operations
- **Bidirectional Communication**: Server-initiated requests
- **Multiplexing**: Multiple operations per connection
- **WebSocket Upgrade**: Future WebSocket support

## Support

For issues or questions about the migration:

1. Check logs for deprecation warnings
2. Test with both HTTP and streaming modes
3. Verify MCP client compatibility
4. Monitor resource usage improvements

The new Streamable HTTP implementation maintains full compatibility while providing a more efficient and scalable foundation for MCP operations.