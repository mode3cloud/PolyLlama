# Debug Tool Visibility Issues

## Problem
Tool calls and outputs are not visible in the UI, even though the implementation appears correct.

## Most Likely Causes

### 1. Model Tools Support Detection (Most Likely)
The code checks if models support tools before including them in the request. For Ollama models, it:
- Calls `/api/show` endpoint
- Looks for "tools" in the capabilities array
- If not found, tools are omitted from the request

**Issue**: Many Ollama models that support function calling don't report "tools" in their capabilities.

### 2. Quick Debugging Steps

Add console logging to see what's happening:

#### Frontend (chatUtils.ts)
After line 105, add:
```typescript
console.log('Received chunk:', chunk);
```

#### Backend (multi_llm_service.py)
Check the logs for these messages:
- "Model X supports tools, including Y tools"
- "Model X does not support tools, omitting Y tools"

## Temporary Workaround

To force tools to be included regardless of capability detection, you can modify `multi_llm_service.py`:

```python
# Line 352, change from:
if tools_spec and await self._model_supports_tools():

# To:
if tools_spec:  # Always include tools if available
```

## Proper Fix

The tool support detection for Ollama models needs improvement. Currently, it relies on the "tools" capability, but this isn't reliable. Options:

1. **Whitelist approach**: Maintain a list of known Ollama models that support tools
2. **Try-and-see approach**: Always send tools and handle errors gracefully
3. **Better detection**: Check for other indicators like "function_calling" in model metadata

## Testing

1. Check browser console for events being received
2. Check backend logs for tool support detection
3. Try the temporary workaround to confirm it's a capability detection issue
4. Check `/ui/api/mcp/status` to ensure MCP tools are loaded

## Common Models That Support Tools

These Ollama models typically support function calling:
- llama3.2:3b
- llama3.1:*
- mistral:*
- mixtral:*
- qwen2.5:*

But they might not report "tools" in their capabilities array.