# PolyLlama Agent Tools

This directory contains the tool integration framework for the PolyLlama agent system.

## Overview

The tool system provides a standardized interface for integrating external services and capabilities into agents. Tools are self-contained, reusable components that agents can invoke to perform specific tasks.

## Architecture

### Core Components

1. **Base Interface (`base.py`)**
   - `Tool`: Abstract base class all tools must implement
   - `ToolResult`: Standardized result format
   - `ToolParameter`: Parameter definitions with validation
   - `ToolError`: Specialized exceptions for tool failures

2. **Registry (`registry.py`)**
   - Central registry for tool discovery and management
   - Usage statistics tracking
   - Category-based organization
   - Tool search capabilities

3. **Executor (`executor.py`)**
   - Retry logic with exponential backoff
   - Result caching for expensive operations
   - Batch execution support
   - Tool chaining for complex workflows

### Tool Categories

- **Email**: Email search, summarization, and drafting
- **Search**: Web search, scraping, and news retrieval
- **Data**: Database queries, data analysis, and file processing

## Creating a New Tool

```python
from tools.base import Tool, ToolResult, ToolStatus, ToolParameter

class MyCustomTool(Tool):
    @property
    def name(self) -> str:
        return "my_custom_tool"
    
    @property
    def description(self) -> str:
        return "Description of what this tool does"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="input",
                type="string",
                description="Input parameter",
                required=True
            )
        ]
    
    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        # Tool implementation
        result = await self.do_something(args["input"])
        
        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={"output": result}
        )
```

## Registering Tools

```python
from tools import get_global_registry
from tools.custom import MyCustomTool

# Get the global registry
registry = get_global_registry()

# Register your tool
registry.register(MyCustomTool(), category="custom")
```

## Using Tools in Agents

```python
from tools import get_global_registry, get_global_executor

# Get registry and executor
registry = get_global_registry()
executor = get_global_executor()

# Execute a tool with retry logic
result = await executor.execute_with_retry(
    tool=registry.get_tool("web_search"),
    args={"query": "PolyLlama documentation"}
)

# Or execute through registry (includes usage tracking)
result = await registry.execute_tool(
    "web_search",
    {"query": "PolyLlama documentation"}
)
```

## Tool Chaining

```python
from tools import ToolChain, get_global_registry

registry = get_global_registry()
chain = ToolChain()

# Chain multiple tools together
chain.add_step(
    tool=registry.get_tool("web_search"),
    args={"query": "latest AI news"}
).add_step(
    tool=registry.get_tool("email_summarize"),
    args={"email_ids": "$step_0.data.results"},  # Reference previous result
    transform=lambda r: {"summary": r.data["summaries"]}
)

# Execute the chain
results = await chain.execute()
```

## API Endpoints

The agent controller exposes the following tool-related endpoints:

- `GET /tools` - List all available tools
- `GET /tools?category=email` - List tools by category
- `GET /tools/{tool_name}` - Get tool details
- `GET /tools/{tool_name}/schema` - Get tool parameter schema
- `POST /tools/{tool_name}/execute` - Execute a tool
- `GET /tools/stats` - Get usage statistics

## Testing

Run tool tests with:

```bash
pytest tests/agent_controller/tools/
```

## Future Enhancements

- [ ] MCP (Model Context Protocol) client integration
- [ ] Tool authorization and access control
- [ ] Streaming support for long-running tools
- [ ] Enhanced metrics and monitoring
- [ ] Tool versioning and migration support
- [ ] Visual tool builder interface