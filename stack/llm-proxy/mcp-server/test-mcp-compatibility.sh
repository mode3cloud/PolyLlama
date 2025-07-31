#!/bin/bash

# Test script to verify MCP server compatibility
echo "🧪 Testing MCP Server Compatibility"
echo "=================================="

MCP_URL="http://localhost:3001/mcp"
SSE_URL="http://localhost:3001/sse"

# Test 1: Health check
echo "1. Health Check..."
curl -s "$MCP_URL/../health" | jq . || echo "Health endpoint test failed"
echo

# Test 2: Initialize request
echo "2. Initialize Request..."
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-init",
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }' | jq . || echo "Initialize test failed"
echo

# Test 3: List tools
echo "3. List Tools..."
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-list",
    "method": "tools/list",
    "params": {}
  }' | jq . || echo "List tools test failed"
echo

# Test 4: SSE streaming format test (if a tool is available)
echo "4. SSE Streaming Format Test..."
echo "Testing streaming with Accept: text/event-stream header..."
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-stream",
    "method": "tools/call",
    "params": {
      "name": "github__search_users",
      "arguments": {"q": "test"}
    }
  }' --max-time 10 || echo "SSE streaming test completed (may have timed out)"
echo

echo "🏁 Test completed!"
echo "Check logs for detailed information about tool execution and response formatting."