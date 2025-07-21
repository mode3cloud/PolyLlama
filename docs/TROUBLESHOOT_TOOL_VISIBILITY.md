# Troubleshooting Tool Visibility in UI

## Quick Checks

### 1. Browser Console
Open browser DevTools and look for:
- `[Chat Stream] Received tool_* event:` messages
- Any JavaScript errors

### 2. Backend Logs
Check docker logs for the llm-proxy service:
```bash
docker logs -f polyllama_llm-proxy_1 | grep -E "(Tool|tool|TOOL)"
```

Look for:
- "Tool support check for [model]: true/false"
- "Ollama model X info: Capabilities: []"
- "Model X does not support tools, omitting Y tools"

### 3. Force Enable Tools (Temporary Fix)
Add to your `.env` file:
```
FORCE_ENABLE_TOOLS=true
```

Then restart the stack. This bypasses tool support detection.

## Common Issues and Solutions

### Issue 1: Model Doesn't Report Tool Support
**Symptom**: Logs show "Model X does not support tools, omitting Y tools"

**Solution**: 
1. Use `FORCE_ENABLE_TOOLS=true` environment variable
2. Or use a model known to support tools:
   - OpenAI: gpt-4, gpt-3.5-turbo
   - Anthropic: claude-3-*
   - Ollama: llama3.2, mistral, mixtral

### Issue 2: No MCP Tools Available
**Symptom**: Logs show "tools available: 0"

**Check**: 
```bash
curl http://localhost:11435/api/mcp/status -H "Authorization: Bearer YOUR_API_KEY"
```

**Solution**: 
1. Check MCP bridge is running
2. Verify MCP servers are configured in docker-compose.yml

### Issue 3: Network/Proxy Buffering
**Symptom**: Events arrive in batches or delayed

**Solution**:
1. Check nginx isn't buffering SSE
2. Ensure no corporate proxy is interfering
3. Try direct connection to llm-proxy port (11435)

## Debug Information Added

### Backend (multi_llm_service.py)
- Enhanced logging for tool support detection
- Added FORCE_ENABLE_TOOLS environment variable
- Better Ollama model capability detection

### Frontend (chatUtils.ts)
- Console logging for all tool-related events
- Shows event type and payload

## Test Commands

### 1. Check if tools are loaded:
```bash
curl http://localhost:11435/api/mcp/tools \
  -H "Authorization: Bearer YOUR_API_KEY" | jq .
```

### 2. Test tool execution directly:
```bash
curl -X POST http://localhost:11435/api/mcp/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "tool_name": "test_tool",
    "arguments": {}
  }'
```

### 3. Check model capabilities:
```bash
# For Ollama models
curl http://localhost:11434/api/show \
  -d '{"name": "llama3.2:3b"}' | jq .capabilities
```

## Expected Flow

1. User sends message
2. Backend logs: "Tool support check for ollama/llama3.2:3b: true"
3. Backend logs: "Model ollama/llama3.2:3b supports tools, including X tools"
4. Browser console: "[Chat Stream] Received tool_call_streaming event"
5. Browser console: "[Chat Stream] Received tool_call event"
6. UI shows: "🔧 Calling tool: **tool_name**"
7. Browser console: "[Chat Stream] Received tool_result event"
8. UI shows tool result

If any step is missing, check the corresponding component.