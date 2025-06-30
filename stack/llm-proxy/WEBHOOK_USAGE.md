# Graphiti Webhook Ingestion Usage Guide

This document explains how to use the webhook ingestion endpoint for Graphiti knowledge integration.

## Endpoint

**URL:** `POST /api/ingest`  
**Authentication:** Protected by `POLYLLAMA_API_KEY` (required in header)

## Request Format

```json
{
  "source_type": "email",
  "text_content": "Meeting scheduled for tomorrow at 10 AM with the product team...",
  "metadata": {
    "sender": "john@example.com",
    "subject": "Product Team Meeting",
    "timestamp": "2024-01-15T10:00:00Z"
  },
  "source_id": "email-12345",
  "timestamp": "2024-01-15T08:30:00Z"
}
```

## Request Fields

- `source_type` (required): Type of source data
  - Supported values: `email`, `meeting_notes`, `document`, `chat`, `web_content`, `file_upload`
- `text_content` (required): The main text content to ingest
- `metadata` (optional): Additional metadata specific to the source type
- `source_id` (optional): Unique identifier for the source item
- `timestamp` (optional): When the content was created/modified

## Response Format

```json
{
  "status": "success",
  "message": "Content from email successfully ingested",
  "ingestion_id": "ing_email_1704176400",
  "processed_at": "2024-01-15T08:35:00Z"
}
```

## cURL Examples

### Basic Email Ingestion
```bash
curl -X POST http://localhost:11434/api/ingest \
  -H "Content-Type: application/json" \
  -H "api-key: your-polyllama-api-key" \
  -d '{
    "source_type": "email",
    "text_content": "Project update: We completed the first phase of development...",
    "metadata": {
      "sender": "team@company.com",
      "subject": "Weekly Project Update"
    }
  }'
```

### Meeting Notes Ingestion
```bash
curl -X POST http://localhost:11434/api/ingest \
  -H "Content-Type: application/json" \
  -H "api-key: your-polyllama-api-key" \
  -d '{
    "source_type": "meeting_notes",
    "text_content": "Action items from today meeting: 1. John to review the proposal, 2. Sarah to prepare the presentation...",
    "metadata": {
      "meeting_title": "Weekly Standup",
      "participants": ["john", "sarah", "mike"]
    },
    "source_id": "meeting-2024-01-15"
  }'
```

### Document Ingestion
```bash
curl -X POST http://localhost:11434/api/ingest \
  -H "Content-Type: application/json" \
  -H "api-key: your-polyllama-api-key" \
  -d '{
    "source_type": "document",
    "text_content": "This technical specification outlines the architecture for the new microservices...",
    "metadata": {
      "title": "Microservices Architecture Spec",
      "author": "Architecture Team",
      "version": "1.2"
    }
  }'
```

## Status Endpoint

**URL:** `GET /api/ingest/status`  
**Authentication:** Protected by `POLYLLAMA_API_KEY`

```bash
curl -X GET http://localhost:11434/api/ingest/status \
  -H "api-key: your-polyllama-api-key"
```

Response:
```json
{
  "status": "healthy",
  "service": "ingestion",
  "graphiti_status": {
    "initialized": true,
    "connected": true,
    "graphiti_url": "http://localhost:8000",
    "namespace": "polyllama",
    "supported_source_types": [
      "email",
      "meeting_notes", 
      "document",
      "chat",
      "web_content",
      "file_upload"
    ]
  },
  "timestamp": "2024-01-15T08:35:00Z"
}
```

## Error Handling

The endpoint returns appropriate HTTP status codes:
- `200` - Success
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (missing/invalid API key)
- `500` - Internal Server Error

Example error response:
```json
{
  "detail": "text_content cannot be empty"
}
```

## Integration Notes

1. **Authentication**: All requests must include the `POLYLLAMA_API_KEY` in one of these headers:
   - `api-key: <your-key>`
   - `x-api-key: <your-key>`
   - `Authorization: Bearer <your-key>`

2. **Rate Limiting**: Consider implementing rate limiting on the client side to avoid overwhelming the service.

3. **Retry Logic**: Implement exponential backoff for failed requests.

4. **Monitoring**: Monitor the `/api/ingest/status` endpoint for service health.

## Webhook Setup Examples

### Email Service Integration
```python
import requests
import json

def send_email_to_graphiti(email_data):
    payload = {
        "source_type": "email",
        "text_content": email_data['body'],
        "metadata": {
            "sender": email_data['from'],
            "subject": email_data['subject'],
            "recipients": email_data['to']
        },
        "source_id": email_data['message_id'],
        "timestamp": email_data['date']
    }
    
    response = requests.post(
        "http://polyllama:11434/api/ingest",
        headers={
            "Content-Type": "application/json",
            "api-key": os.getenv("POLYLLAMA_API_KEY")
        },
        json=payload
    )
    
    return response.json()
```

### Slack Bot Integration
```javascript
const axios = require('axios');

async function sendSlackMessageToGraphiti(message) {
  const payload = {
    source_type: 'chat',
    text_content: message.text,
    metadata: {
      channel: message.channel,
      user: message.user,
      thread_ts: message.thread_ts
    },
    source_id: message.ts,
    timestamp: new Date(message.ts * 1000).toISOString()
  };

  try {
    const response = await axios.post('http://polyllama:11434/api/ingest', payload, {
      headers: {
        'Content-Type': 'application/json',
        'api-key': process.env.POLYLLAMA_API_KEY
      }
    });
    return response.data;
  } catch (error) {
    console.error('Failed to send to Graphiti:', error);
    throw error;
  }
}
```