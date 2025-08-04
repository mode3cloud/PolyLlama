# PolyLlama Active Context

## Current Work Focus

### Recent Architecture Evolution
Based on git history, the project recently underwent significant refactoring:
- **Removed agent-controller**: Eliminated multi-agent complexity in favor of focused single-agent approach
- **MCP Integration**: Strengthened Model Context Protocol integration for tool capabilities
- **Streamable HTTP**: Migrated MCP server to Node.js with improved streaming support
- **Tool Streaming**: Enhanced real-time tool execution feedback in UI

### Critical Active Patterns

#### MCP Server Implementation Status
**CRITICAL CONSTRAINT**: Single-event SSE format is mandatory for MCP client compatibility
- **File**: `stack/llm-proxy/mcp-server/server.py`
- **Pattern**: Execute tool completely, then send single final result
- **Reason**: mcpinspection v0.16.1 and other MCP clients hang on multi-event streams
- **Testing**: Use `curl` for HTTP testing, `mcpinspection` for MCP compliance

#### API Security Enforcement
**Active Pattern**: Strict API key protection on all public endpoints
- **Protected**: All `/api/*` endpoints except `/api/polyllama/*` (internal UI)
- **Headers**: `api-key`, `x-api-key`, `Authorization: Bearer`
- **Implementation**: Nginx Lua `access_by_lua_block`
- **LiteLLM Integration**: Automatic API key passthrough when calling Ollama

### Current Development Priorities

#### 1. System Stability & Integration
- **MCP Server**: Maintain single-event SSE streaming compatibility
- **API Security**: Ensure all public endpoints properly protected
- **Configuration Preservation**: Never modify `mcp-config.json` without permission

#### 2. Tool Integration Maturity
- **Real-time Feedback**: Tool execution streaming to UI complete
- **Error Handling**: Comprehensive tool error display and recovery
- **MCP Protocol**: Full compliance with Model Context Protocol standards

#### 3. User Experience Refinement
- **Dashboard Monitoring**: Real-time GPU metrics and instance status
- **Model Management**: Streamlined loading, unloading, and browsing
- **Chat Interface**: Multi-provider support with tool integration

## Active Technical Decisions

### Package Management Standards
- **Python**: Using `uv` for all dependency management
- **JavaScript**: Using `pnpm` for Next.js UI components
- **Testing**: `pytest` with `uv run pytest` execution pattern

### Service Communication Patterns
**Established Pattern**: Layered proxy architecture
- Browser → Nginx (`:11434`) → Service routing
- `/api/*` → Direct Ollama instance routing
- `/ui/api/*` → Next.js API routes → LLM Proxy (`:11435`)

**Critical Rule**: Client browsers never access Docker service names directly

### Streaming Response Handling
**Two Patterns in Use**:
1. **Simple Pass-through**: Direct proxy without processing
2. **Transform Stream**: Server-side processing with `TransformStream`

**Critical Implementation Note**: Never call `response.body.getReader()` before `pipeThrough()` - it locks the stream

## Current System State

### Production-Ready Components
- **Hardware Detection**: Robust GPU detection and grouping
- **Template Generation**: Dynamic Docker Compose and Nginx configuration
- **Load Balancing**: Intelligent model-to-instance routing
- **Web UI**: Full-featured dashboard and model management
- **MCP Integration**: Tool execution with streaming feedback

### Known Working Configurations
- **Multi-GPU Workstations**: Different GPU types properly grouped
- **Single GPU Systems**: Optimal single-instance deployment
- **CPU-Only Systems**: Fallback CPU instance creation
- **Mixed Deployments**: GPU + CPU instance combinations

### Active Monitoring Points
- **Instance Health**: Real-time status checking
- **Model Distribution**: Load balancing effectiveness
- **Tool Execution**: MCP tool streaming performance
- **API Security**: Key validation and endpoint protection

## Recent Learning & Insights

### MCP Protocol Evolution
- Single-event streaming is non-negotiable for client compatibility
- Tool execution feedback greatly improves user experience
- OpenAI format consistency across all streaming responses

### Architecture Simplification Benefits
- Removing multi-agent complexity improved maintainability
- Focused single-agent approach with rich tool integration more effective
- Clear service boundaries reduce debugging complexity

### User Experience Findings
- Hardware auto-detection eliminates major adoption barrier
- Real-time tool execution feedback crucial for trust
- Single API endpoint simplifies integration significantly

## Immediate Considerations

### Development Workflow
- Always use `uv run pytest` for testing
- Preserve user `mcp-config.json` configurations
- Test MCP compatibility with both curl and mcpinspection
- Maintain API key protection on all public endpoints

### Code Quality Standards
- Server-side only Docker service communication
- Comprehensive error handling for tool executions
- Structured logging with request correlation
- Performance monitoring for routing decisions

### Configuration Management
- Environment variables drive deployment behavior
- Template generation must remain hardware-driven
- User configurations preserved across development sessions
- Security settings enforced consistently

The project is in a stable, production-ready state with active focus on maintaining compatibility standards and enhancing user experience through better tool integration and monitoring capabilities.