# MCP Tool Streaming UI Fixes

## Issues Fixed

### 1. Duplicate Assistant Messages
**Problem**: The assistant's response was appearing both above and below the tool execution.

**Root Cause**: When tool results were received, the code was creating a new empty assistant message instead of continuing with the existing one.

**Fix**: Modified the message handling to:
- Use `findLastIndex` to locate and update the last assistant message during streaming
- Replace (not append) assistant messages when showing tool calls
- Continue streaming to the same assistant message after tool execution

### 2. Tool Response Formatting
**Problem**: Tool results were displayed as plain text instead of formatted JSON.

**Root Cause**: The raw JSON response from tools wasn't being formatted for display.

**Fix**: Added JSON formatting in `onToolResult`:
```javascript
// Format the result - try to parse as JSON for better display
let formattedResult = result;
try {
  const parsed = JSON.parse(result);
  formattedResult = '```json\n' + JSON.stringify(parsed, null, 2) + '\n```';
} catch {
  // Not JSON, use as-is
}
```

## Updated Message Flow

1. **User sends message**
2. **Assistant message created** (empty, will accumulate content)
3. **If tool needed:**
   - Replace assistant message with "Preparing to call tool..."
   - Replace with "Calling tool: X" with arguments
   - Add tool result message (formatted as JSON if applicable)
4. **Assistant continues** streaming to the original assistant message
5. **Final result**: Clean message flow without duplicates

## Key Changes

### ChatInterface.tsx
- **onChunk**: Now finds and updates the last assistant message instead of assuming it's at the end
- **onToolCallStreaming**: Replaces the last assistant message instead of appending
- **onToolCall**: Replaces the last assistant message with tool call details
- **onToolResult**: Formats JSON results and doesn't create a new assistant message

### Test Files
- `test_mcp_streaming.py`: Backend streaming verification
- `test_ui_tool_rendering.html`: Visual UI rendering test

## Testing

To verify the fixes:

1. Start the polyllama stack
2. Open the chat UI
3. Ask a question that triggers tool usage (e.g., "What's the weather?")
4. Verify:
   - No duplicate assistant messages
   - Tool results display as formatted JSON
   - Assistant continues naturally after tool execution