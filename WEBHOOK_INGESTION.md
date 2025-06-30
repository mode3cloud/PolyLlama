# Webhook Ingestion for Graphiti Knowledge Integration

This document describes the webhook ingestion system for automated knowledge graph ingestion into PolyLlama via Graphiti.

## Overview

The webhook ingestion system allows external services to automatically submit content to PolyLlama's knowledge graph through standardized HTTP endpoints. Content is processed via MCP (Model Context Protocol) tools and ingested into Graphiti for knowledge extraction and analysis.

## Architecture

```
External Service → POST /api/ingest → LLM Proxy → MCP Bridge → Graphiti MCP Server → Knowledge Graph
```

### Components

1. **Ingestion API Endpoint** (`/api/ingest`)
   - FastAPI endpoint in `stack/llm-proxy/api/ingestion.py`
   - Protected by POLYLLAMA_API_KEY authentication
   - Validates input and handles error cases

2. **Graphiti MCP Server** (`stack/mcp-servers/graphiti/`)
   - Custom MCP server providing `add_episodes` tool
   - Python-based server using MCP SDK
   - Handles knowledge graph ingestion operations

3. **MCP Bridge Integration**
   - Existing MCP bridge automatically discovers and exposes Graphiti tools
   - No code changes needed to existing MCP infrastructure

## API Endpoints

### POST /api/ingest

Main webhook endpoint for content ingestion.

**Authentication**: Requires `api-key` header with valid POLYLLAMA_API_KEY

**Request Body**:
```json
{
  "source_type": "email|meeting_notes|document|chat|web_content|file_upload",
  "text_content": "The content to be processed...",
  "title": "Optional content title",
  "author": "Optional author name",
  "source_url": "Optional source URL",
  "timestamp": "Optional ISO 8601 timestamp",
  "tags": ["optional", "tags", "list"],
  "priority": "low|medium|high",
  "custom_metadata": {
    "any": "additional metadata"
  }
}
```

**Response**:
```json
{
  "success": true,
  "message": "Content successfully ingested into knowledge graph",
  "episode_id": "ep_123_1234567890",
  "entities_extracted": 15,
  "relationships_created": 8,
  "processed_at": "2023-12-07T10:30:00Z"
}
```

### GET /api/ingest/status

Health check endpoint for the ingestion service.

**Response**:
```json
{
  "status": "healthy|degraded|error",
  "mcp_connected": true,
  "graphiti_available": true,
  "tools_count": 2,
  "uptime": "unknown"
}
```

## Usage Examples

### Basic Content Ingestion

```bash
curl -X POST "http://localhost:11434/api/ingest" \
  -H "Content-Type: application/json" \
  -H "api-key: your-polyllama-api-key" \
  -d '{
    "source_type": "email",
    "text_content": "Meeting notes from today: We discussed the Q4 roadmap and decided to prioritize the user authentication feature. John will lead the backend implementation while Sarah handles the frontend.",
    "title": "Q4 Roadmap Meeting",
    "author": "meeting-bot",
    "timestamp": "2023-12-07T10:30:00Z",
    "tags": ["meeting", "roadmap", "q4"],
    "priority": "high"
  }'
```

### Email Integration

```bash
curl -X POST "http://localhost:11434/api/ingest" \
  -H "Content-Type: application/json" \
  -H "api-key: your-polyllama-api-key" \
  -d '{
    "source_type": "email",
    "text_content": "Hi team, I wanted to follow up on our discussion about the API rate limiting. Based on our analysis, I recommend implementing a token bucket algorithm...",
    "title": "API Rate Limiting Discussion",
    "author": "jane.doe@company.com",
    "timestamp": "2023-12-07T14:15:00Z",
    "tags": ["api", "rate-limiting", "technical"],
    "priority": "medium",
    "custom_metadata": {
      "email_id": "msg_abc123",
      "thread_id": "thread_xyz789",
      "recipients": ["team@company.com"]
    }
  }'
```

### Document Upload

```bash
curl -X POST "http://localhost:11434/api/ingest" \
  -H "Content-Type: application/json" \
  -H "api-key: your-polyllama-api-key" \
  -d '{
    "source_type": "document",
    "text_content": "Project Requirements Document\n\n1. Overview\nThis document outlines the requirements for the new customer portal...",
    "title": "Customer Portal Requirements",
    "author": "product-team",
    "tags": ["requirements", "portal", "customer"],
    "priority": "high",
    "custom_metadata": {
      "document_type": "requirements",
      "version": "1.0",
      "department": "product"
    }
  }'
```

### Status Check

```bash
curl -X GET "http://localhost:11434/api/ingest/status" \
  -H "api-key: your-polyllama-api-key"
```

## Configuration

### MCP Server Configuration

The Graphiti MCP server is configured in `mcp-config.json`:

```json
{
  "mcpServers": {
    "graphiti": {
      "command": "./stack/mcp-servers/graphiti/run.sh",
      "args": [],
      "env": {
        "PYTHONPATH": "./stack/mcp-servers/graphiti"
      }
    }
  }
}
```

### Environment Variables

- `POLYLLAMA_API_KEY`: Required for API authentication
- `MCP_BRIDGE_URL`: URL of the MCP bridge service (default: `http://mcp-bridge:3000`)

## Error Handling

### Common Error Responses

**Missing API Key** (401):
```json
{
  "detail": "Unauthorized"
}
```

**Invalid Input** (422):
```json
{
  "detail": [
    {
      "loc": ["body", "source_type"],
      "msg": "string does not match regex",
      "type": "value_error.str.regex"
    }
  ]
}
```

**Service Unavailable** (503):
```json
{
  "success": false,
  "message": "Failed to process content",
  "error": "MCP service not available"
}
```

**Processing Error** (200 with success: false):
```json
{
  "success": false,
  "message": "Failed to process content", 
  "error": "Tool execution failed: Invalid content format"
}
```

## Development and Testing

### Running the Graphiti MCP Server

```bash
# Make the run script executable (if not already)
chmod +x ./stack/mcp-servers/graphiti/run.sh

# Install dependencies
cd ./stack/mcp-servers/graphiti
pip install -r requirements.txt

# Run the server (usually handled automatically by MCP bridge)
python3 server.py
```

### Testing the Integration

1. **Check Service Status**:
   ```bash
   curl -X GET "http://localhost:11434/api/ingest/status" \
     -H "api-key: your-api-key"
   ```

2. **Test Basic Ingestion**:
   ```bash
   curl -X POST "http://localhost:11434/api/ingest" \
     -H "Content-Type: application/json" \
     -H "api-key: your-api-key" \
     -d '{"source_type": "chat", "text_content": "Test message"}'
   ```

3. **Check MCP Tools**:
   ```bash
   curl -X GET "http://localhost:11434/api/mcp/tools" \
     -H "api-key: your-api-key"
   ```

### Debugging

**Check MCP Bridge Status**:
```bash
curl -X GET "http://localhost:11434/api/mcp/status" \
  -H "api-key: your-api-key"
```

**View MCP Bridge Logs**:
```bash
docker-compose -f builder/built/docker-compose.yml logs mcp-bridge
```

**View LLM Proxy Logs**:
```bash
docker-compose -f builder/built/docker-compose.yml logs llm-proxy
```

## Integration Examples

### Zapier Integration

Use Zapier's webhook action to send content to the ingestion endpoint:

1. Trigger: Your desired trigger (new email, form submission, etc.)
2. Action: Webhooks by Zapier - POST
3. URL: `http://your-polyllama-instance:11434/api/ingest`
4. Headers: `api-key: your-polyllama-api-key`
5. Body: Map your data to the required JSON structure

### Python Integration

```python
import requests
import json

def ingest_content(api_key, content, source_type="document", **metadata):
    """Ingest content into PolyLlama knowledge graph."""
    
    url = "http://localhost:11434/api/ingest"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    payload = {
        "source_type": source_type,
        "text_content": content,
        **metadata
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# Example usage
result = ingest_content(
    api_key="your-api-key",
    content="Meeting summary: We discussed the new feature...",
    source_type="meeting_notes",
    title="Weekly Team Meeting",
    tags=["meeting", "weekly", "team"]
)

print(f"Ingestion result: {result}")
```

### Node.js Integration

```javascript
const axios = require('axios');

async function ingestContent(apiKey, content, sourceType = 'document', metadata = {}) {
  try {
    const response = await axios.post('http://localhost:11434/api/ingest', {
      source_type: sourceType,
      text_content: content,
      ...metadata
    }, {
      headers: {
        'Content-Type': 'application/json',
        'api-key': apiKey
      }
    });
    
    return response.data;
  } catch (error) {
    console.error('Ingestion failed:', error.response?.data || error.message);
    throw error;
  }
}

// Example usage
ingestContent(
  'your-api-key',
  'Customer feedback: The new interface is much more intuitive...',
  'web_content',
  {
    title: 'Customer Feedback',
    author: 'feedback-system',
    tags: ['feedback', 'ui', 'customer'],
    priority: 'medium'
  }
).then(result => {
  console.log('Ingestion successful:', result);
}).catch(error => {
  console.error('Ingestion failed:', error);
});
```

## Supported Source Types

- **email**: Email messages and newsletters
- **meeting_notes**: Meeting summaries and notes
- **document**: Formal documents and files
- **chat**: Chat messages and conversations
- **web_content**: Web pages and articles
- **file_upload**: User-uploaded files and content

## Security Considerations

1. **API Key Protection**: Always use HTTPS in production and keep API keys secure
2. **Content Validation**: All input is validated and sanitized before processing
3. **Rate Limiting**: Consider implementing rate limiting for webhook endpoints
4. **Content Size Limits**: Text content is limited to 100KB per request
5. **Metadata Validation**: All metadata fields are validated and limited in size

## Future Enhancements

- **Batch Ingestion**: Support for multiple content items in a single request
- **Async Processing**: Queue-based processing for large content volumes
- **Content Deduplication**: Automatic detection and handling of duplicate content
- **Real Graphiti Integration**: Replace placeholder implementation with actual Graphiti client
- **Enhanced Metadata**: Support for richer metadata schemas
- **Webhook Subscriptions**: Callbacks for ingestion status updates