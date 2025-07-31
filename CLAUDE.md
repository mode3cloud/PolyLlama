# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


**IMPORTANT**: The official 2025-06-18 MCP scehma is provided in mcp-server/official-mcp-transport-specification-2025-06-18.json If there are any backwards compatibility issues with MCP clients we consume, or servers that consume us, we can reference https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/schema/2025-03-26/schema.json to understand the issues.

## Primary Agent Approach

You are the lead architect for PolyLlama, a dynamic multi-instance Ollama orchestration system.
You have deep understanding of the entire system architecture including hardware detection, routing, and single-agent tool integration.
Refer to this CLAUDE.md for system guidelines and architectural principles.

## Architecture Overview

PolyLlama is a dynamic multi-instance Ollama orchestration system that automatically detects hardware and generates optimal deployments. The core architecture consists of:

### Dynamic Generation System
- **Hardware Detection**: `polyllama.sh` uses `nvidia-smi` to detect GPUs and group them by type
- **Template Rendering**: `builder/generator.py` renders templates based on detected hardware
- **Output**: Generates `builder/built/docker-compose.yml` and `builder/built/nginx.conf`
- **Structure**: Only generated files are placed in `builder/built/`, Dockerfiles remain in `stack/`

### Request Routing Architecture
- **Entry Point**: Nginx router (`stack/polyllama/`) serves as the single API endpoint at `:11434`
- **Smart Routing**: `model_router.lua` implements intelligent model-to-instance routing with:
  - Least-loaded instance assignment for new models
  - Model state tracking via shared memory (`model_mappings`)
  - Dynamic upstream generation based on instance count
  - Instance availability checking before routing
  - CPU routing modes: `prefer_gpu` (default), `balanced`, `gpu_only`
- **Instance Naming**: Uses `polyllama1`, `polyllama2`, etc. (not `ollama1`)

### Template System
The system uses a custom template renderer (not Jinja2) that handles:
- `{% for instance in ollama_instances %}` loops
- `{{ instance.property }}` variable substitution
- `{% if instance.gpu_indices %}` conditionals

Templates are in:
- `builder/docker-compose.yml.j2` → `builder/built/docker-compose.yml`
- `builder/nginx.conf.j2` → `builder/built/nginx.conf`

### Web UI and API Architecture
**CRITICAL: All API calls must be server-side only. Client browsers cannot access Docker service names.**

The system exposes a unified interface on port `:11434`:
- `/api/*` - Routed by Nginx to appropriate Ollama instances via Lua logic
- `/ui/*` - Proxied to Next.js app running on port 3000

**IMPORTANT: Nginx strips the `/ui` prefix when proxying to Next.js**
- Nginx receives: `http://localhost:11434/ui/something`
- Next.js receives: `http://localhost:3000/something`
- This means Next.js routes must be structured without the `/ui` prefix

**Next.js Route Structure:**
```
app/
├── page.tsx                    # Dashboard (/)
├── chat/
│   └── page.tsx               # Chat interface (/chat)
├── email/
│   └── page.tsx               # Email interface (/email)
└── api/
    ├── chat/                  # LLM proxy endpoints
    │   ├── route.ts          # /api/chat
    │   └── models/
    │       └── route.ts      # /api/chat/models
    └── email/                 # Email AI endpoints
        ├── summarize/
        │   └── route.ts      # /api/email/summarize
        ├── draft/
        │   └── route.ts      # /api/email/draft
        └── sessions/
            └── route.ts      # /api/email/sessions
```

**API Communication Patterns:**
1. **Ollama API Access** (Dashboard/Monitoring):
   - UI components use `/api/*` endpoints (e.g., `/api/models`, `/api/generate`)
   - These are routed by Nginx to the appropriate Ollama instance
   - Example: `fetch('/api/models')` from the UI hits `localhost:11434/api/models`

2. **LLM Proxy Access** (Chat/Email AI features):
   - Client-side code uses `/ui/api/*` endpoints for Next.js API routes
   - Next.js server-side routes proxy to `http://llm-proxy:11435`
   - This enables multi-provider support (OpenAI, Anthropic, etc.) via litellm
   - Example from browser: `fetch('/ui/api/chat/models')` → Next.js API → `http://llm-proxy:11435/api/models`

**Key Design Principles:**
- Never make direct calls to Docker service names from client-side code
- All inter-service communication happens server-side
- Client-side code uses `/ui/api/*` for Next.js API routes (Chat, Email AI features)
- Client-side code uses `/api/*` for direct Ollama access (Dashboard monitoring)
- LLM proxy may internally call back to Ollama via `localhost:11434/api/*`

**Streaming Response Patterns:**
1. **Simple Pass-through** (Chat routes):
   - When proxying without server-side processing
   - Returns the response stream directly to the client
   - Example: `/api/chat/route.ts`
   ```typescript
   if (body.stream && response.ok) {
     return new NextResponse(response.body, {
       headers: {
         'Content-Type': 'text/event-stream',
         'Cache-Control': 'no-cache',
         'Connection': 'keep-alive',
       },
     })
   }
   ```

2. **Transform Stream** (Email routes):
   - When server needs to process/accumulate content
   - Uses TransformStream to intercept and modify the stream
   - Example: `/api/email/summarize/route.ts`, `/api/email/draft/route.ts`
   ```typescript
   const stream = new TransformStream({
     async transform(chunk, controller) {
       // Process chunk, accumulate content, etc.
       controller.enqueue(chunk)
     }
   })
   const transformedStream = response.body.pipeThrough(stream)
   ```
   - **Important**: Never call `response.body.getReader()` before `pipeThrough()` as it locks the stream

**API Key and Authentication Patterns:**
- When accessing `/api/*` endpoints: This is proxied by NGINX lua to a specific backend Ollama instance and MUST be protected by the API-KEY header. It should NEVER be removed. We use this `/api/*` as if it were a transparent single Ollama instance, but it is exposed publicly, so enforcement of an API-KEY is critical.

- When making client calls to `/ui/api/*`: These are NextJS SSE endpoints protected with a JWT, using OAuth to provide identity confirmation before issuing a JWT. Even though we have passed JWT auth when calling `/ui/api/*`, any internal calls to `/api/*` for Ollama must also include the API-KEY to prevent compromising the security of that as an open endpoint.

## Common Commands

### Launch and Management
```bash
# Auto-detect hardware and launch stack
./polyllama.sh

# Show hardware detection without launching
./polyllama.sh --detect

# Debug mode - show build output on console instead of log file
./polyllama.sh --debug

# Force rebuild of Docker images (no cache)
./polyllama.sh --build

# Stop all services
./polyllama.sh --stop

# View logs from all services
./polyllama.sh --logs

# Check status of all services
./polyllama.sh --status
```

### Development and Testing
```bash
# Run complete test suite
./tests/run_tests.sh

# Run tests with pytest (VS Code integration)
uv run pytest tests/
uv run pytest tests/test_generation.py::test_cpu_only -v

# Run legacy standalone scripts
python3 tests/test_generation.py
python3 tests/test_edge_cases.py

# Manual template generation (for testing)
python3 builder/generate_compose.py '{"gpu_groups":[{"name":"RTX 4090","indices":[0,1,2]}]}'

# Install dependencies
uv sync
```

### Direct Service Management
```bash
# Use generated compose file for manual control
docker compose -f builder/built/docker-compose.yml up -d
docker compose -f builder/built/docker-compose.yml logs polyllama1
docker compose -f builder/built/docker-compose.yml ps
```

## Instance Count Propagation

The `OLLAMA_INSTANCE_COUNT` environment variable flows through the system:
1. Set in router service environment in `builder/built/docker-compose.yml`
2. Read by nginx `init_by_lua_block` into shared memory (`env_vars`)
3. Used by `model_router.lua` via `get_instance_count()` function
4. JavaScript UI reads via `/api/polyllama/instance-count` endpoint

## Model Routing Logic

Models are routed using this hierarchy:
1. **Existing running model**: Route to instance where model is already loaded
2. **Cached mapping**: Use stored model-to-instance mapping from shared memory
3. **Least loaded assignment**: Assign to instance with fewest models
4. **Loading locks**: Prevent duplicate model loading across instances

### CPU Routing Behavior

The system supports mixed GPU+CPU deployments with configurable routing behavior:

- **Default (`prefer_gpu`)**: Routes to GPU instances when available, only uses CPU instances as fallback
- **Balanced mode**: Treats all instances equally for load distribution
- **GPU-only mode**: Never routes to CPU instances automatically

When GPU instances are available, CPU instances are NOT automatically used unless:
1. All GPU instances are offline/unavailable
2. User explicitly maps a model to CPU via UI
3. Routing mode is set to `balanced`

Environment variables:
- `POLYLLAMA_CPU_INSTANCES`: Number of CPU instances to create (default: 0)
- `POLYLLAMA_MIXED_MODE`: Enable mixed GPU+CPU deployment (default: false)
- `POLYLLAMA_CPU_ROUTING_MODE`: Routing preference (default: prefer_gpu)

## Key Files for Modifications

### Hardware Detection
- `polyllama.sh`: Main detection logic using `nvidia-smi`
- Modify `detect_gpu_groups()` function for new hardware types

### Template Rendering
- `builder/generator.py`: Core generation logic
- `builder/docker-compose.yml.j2`: Service definitions template
- `builder/nginx.conf.j2`: Nginx configuration template

### Routing Logic
- `stack/polyllama/model_router.lua`: Request routing and load balancing
- `stack/polyllama/script.js`: Web UI for monitoring and control

### Testing
- `tests/test_generation.py`: Main test scenarios (2-6 GPU groups, CPU-only)
- `tests/test_edge_cases.py`: Edge cases (single GPU, large configs, empty groups)
- `tests/test_cpu_routing.py`: CPU routing behavior and instance availability

## Debugging Tips

### Generation Issues
- Check `polyllama-compose-build.log` for build errors
- Use `--debug` flag to see build output on console
- Manually run generation script with test configs

### Routing Issues
- Check nginx error logs in router container
- Examine shared memory state via `/api/polyllama/model-mappings`
- Verify `OLLAMA_INSTANCE_COUNT` propagation

### Service Communication
- Ensure all `polyllamaX` services can resolve each other via Docker networks
- Check that nginx upstream pool matches actual running services
- Verify GPU assignments in container environment variables

## API Key Protection

When `POLYLLAMA_API_KEY` is set in the `.env` file:
- All `/api/*` endpoints are protected (except `/api/polyllama/*` which are internal UI endpoints)
- Authentication is required via one of these headers:
  - `api-key: <your_api_key>`
  - `x-api-key: <your_api_key>`
  - `Authorization: Bearer <your_api_key>`
- The protection is implemented in nginx using Lua access_by_lua_block
- LiteLLM proxy automatically passes the API key when calling Ollama endpoints

Implementation details:
- API key check is done in `builder/nginx.conf.j2` for each protected endpoint
- The router service loads the API key from the .env file via env_file directive
- LiteLLM proxy adds the API key as `api-key` header when calling Ollama models

## Development Guidelines

### Package Management
- We use **pnpm** NOT npm for Next.js/UI components
- We use **uv** for Python dependency management in agent-controller

### Testing
- Use **pytest** for Python tests in the agent-controller service
- Run tests with: `uv run pytest tests/agent_controller/`
- All new tools must include unit and integration tests

### Agent Development Progress Tracking
- **IMPORTANT**: Always maintain a todo list using the TodoWrite tool when working on multi-step implementations
- Track progress frequently as tasks are completed and new ones arise
- Use the todo list to organize complex tasks and ensure nothing is forgotten

### Single-Agent Implementation Status

**Overall Progress: Phase 2 Complete (Phase 1: ✅ | Phase 2: ✅)**

**Recent Completions:**
- ✅ **Tool Integration Framework**: Complete tool system with 12+ modules
- ✅ **Security & Auth**: RBAC, audit logging, API key protection
- ✅ **Monitoring**: Comprehensive metrics and performance tracking  
- ✅ **Developer Experience**: Auto-documentation, testing, streaming support

**Current Priorities:**
1. Next.js API route integration (pending from Phase 1)
2. Full session persistence improvements
3. Advanced prompt engineering and context management

**Ready for Production:**
- Tool execution and discovery
- Authentication and authorization
- Metrics and monitoring
- Streaming tool support
- MCP protocol integration

# PolyLlama Single-Agent Implementation Plan

## Overview

This document provides a comprehensive implementation plan for the single-agent architecture in PolyLlama while preserving the existing multi-instance Ollama architecture, security patterns, and routing logic.

## Architecture Overview

### Core Principles

- **No Disruption**: Maintain existing Nginx/Lua routing logic unchanged
- **Server-Side Only**: All agent/tool operations must be server-side (no browser-based tool calls)
- **Security First**: Preserve API-KEY and JWT/OAuth patterns on all endpoints
- **Focused**: Build robust single-agent flows with comprehensive tool support
- **Streaming First**: Support progressive feedback at every layer

### High-Level Architecture

```
[Browser] → [Next.js /ui/api/agent/*] → [Agent Controller :11436] → [LLM Proxy :11435] → [Ollama :11434]
                                              ↓
                                         [MCP Tools/Services]
```

### Detailed Component Flow

```
+---------------------------------------------------------------------------------------+
|                                       User                                            |
|                    (PolyLlama UI: /chat, /email, etc)                                |
+--------------------------------------+------------------------------------------------+
                                       |
                                       | 1. Prompt/Query
                                       v
+-----------------------------------[ Next.js API Layer ]-------------------------------+
|  /ui/api/agent/* (chat, email, workflow)                                            |
|   - Receives user prompt                                                            |
|   - Manages JWT auth                                                                |
|   - Streams partial outputs to browser (Server-Sent Events / HTTP chunking)          |
|   - Calls Agent Controller Service                                                  |
+--------------------------------------+------------------------------------------------+
                                       |
                                       | 2. Full prompt/context/session_id
                                       v
+-----------------------------[ Agent Controller Service (Python) ]---------------------+
|   Port: 11436 (internal only)                                                       |
|   - Session memory (per user/conversation)                                          |
|   - Implements single agent with planning capabilities                              |
|   - Streaming support: yields partial LLM or agent output back to API               |
|   - Orchestrates workflow:                                                          |
|        a) Plan/Reason (CoT, ReACT, etc)                                            |
|        b) Decide which tool to call                                                 |
|        c) Invoke LLM via LLM Proxy (litellm)                                       |
|        d) Execute tools as needed                                                   |
|        e) Generate results                                                          |
+--------------------------------------------------------------------------------------+
                                       |
                                       | 3. Calls LLM Proxy
                                       v
+-----------------------------[ LLM Proxy (litellm) :11435 ]---------------------------+
|   - Multi-provider support (OpenAI, Anthropic, Ollama, etc.)                        |
|   - Streaming support                                                               |
|   - Forwards Ollama requests to localhost:11434 with API-KEY                        |
+--------------------------------------+------------------------------------------------+
                                       |
                                       | 4. Ollama requests (when needed)
                                       v
+-----------------------------[ Nginx Router + Ollama :11434 ]--------------------------+
|   - API-KEY protected endpoints                                                     |
|   - Lua-based model routing to appropriate instance                                 |
|   - Multiple Ollama instances (polyllama1, polyllama2, etc.)                       |
+--------------------------------------------------------------------------------------+
```

## Implementation Components

### 1. Agent Controller Service (NEW)

**Location**: `stack/agent-controller/`
**Port**: 11436 (internal only)
**Technology**: Python FastAPI with async support

**Responsibilities**:
- Orchestrate LLM workflows using PolyLlama backend via LLM proxy
- Manage agent sessions and conversation state
- Interface with MCP tools and external services
- Handle turn-taking and context management
- Support streaming responses for real-time feedback

### 2. Tool Registry (NEW)

**Location**: `stack/agent-controller/tools/`

Standardized tool interface for all integrations:
- Each MCP/external service wrapped as Python callable
- Consistent interface: `async def tool(args: dict) -> dict`
- Central registry for tool discovery and metadata
- Tools invoked by agent code, not LLM directly
- Support for streaming tools where applicable

### 3. Session Management

**Storage**: Redis or PostgreSQL (not in-memory)
**Session Schema**:
```json
{
  "session_id": "uuid",
  "agent_type": "chat|workflow|email",
  "context": [...],
  "tools_used": [...],
  "state": "active|paused|complete",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

## Implementation Progress

### ✅ Phase 1: Single-Agent Foundation (COMPLETED)

**Status: COMPLETE** - Basic agent infrastructure established.

**Completed Components:**
1. **Agent Controller Service** - FastAPI service at port 11436
   - Located in `stack/agent-controller/main.py`
   - Streaming chat endpoint `/agent/chat`
   - Status and health endpoints
   - Integrated with tool registry

2. **Core Agent Architecture**
   - Base agent class in `stack/agent-controller/agents/base.py`
   - Chat agent implementation in `stack/agent-controller/agents/chat.py`
   - Session management in `stack/agent-controller/core/session.py`
   - LLM client integration in `stack/agent-controller/core/llm_client.py`

3. **Configuration and Dependencies**
   - FastAPI with async support and CORS
   - Structured logging with structlog
   - Configuration management
   - Docker integration ready

**Pending in Phase 1:**
- [ ] Next.js API route integration (`/ui/api/agent/*`)
- [ ] Full session persistence (currently basic implementation)
- [ ] Advanced prompt engineering and context management

### ✅ Phase 2: Tool Integration (COMPLETED)

**Status: COMPLETE** - Comprehensive tool framework implemented.

**Completed Components:**

1. **Core Tool Infrastructure** (100% Complete)
   - ✅ `base.py` - Abstract Tool class with validation and timeout support
   - ✅ `registry.py` - Centralized tool management with usage tracking
   - ✅ `executor.py` - Retry logic, caching, and batch execution
   - ✅ API endpoints for tool discovery and execution

2. **Tool Implementations** (100% Complete)
   - ✅ **Email Tools**: `EmailSearchTool`, `EmailSummarizeTool`, `EmailDraftTool`
   - ✅ **Search Tools**: `WebSearchTool`, `WebScrapeTool`, `NewsSearchTool`  
   - ✅ **Data Tools**: `DatabaseQueryTool`, `DataAnalysisTool`, `FileDataTool`

3. **Advanced Features** (100% Complete)
   - ✅ **MCP Integration**: `mcp_client.py` with HTTP and mock transports
   - ✅ **Result Formatting**: Multiple output formats (Standard, Agent, Human, JSON)
   - ✅ **Metrics & Analytics**: Performance tracking and usage statistics
   - ✅ **Authentication & Authorization**: RBAC with audit logging
   - ✅ **Streaming Support**: Real-time progress updates for long-running tools
   - ✅ **Documentation Generator**: Auto-generated docs and OpenAPI specs

4. **Testing Infrastructure** (100% Complete)
   - ✅ Unit tests for base interfaces (`test_base.py`)
   - ✅ Integration tests for tool workflows (`test_registry.py`, `test_email_integration.py`)
   - ✅ Mock implementations for development

**Key Achievements:**
- **20/20 Todo Items Completed** 
- **12 New Tool Modules** with full functionality
- **Production-Ready Security** with role-based access control
- **Comprehensive Monitoring** with metrics and audit logging
- **Extensible Architecture** for easy tool addition

**API Endpoints Added:**
- `GET /tools` - List available tools
- `GET /tools/{tool_name}` - Get tool details  
- `POST /tools/{tool_name}/execute` - Execute tool
- `GET /tools/stats` - Usage statistics

**No Pending Items in Phase 2** - All planned functionality delivered.

## Current File Structure

```
stack/
├── agent-controller/                    # ✅ IMPLEMENTED
│   ├── Dockerfile                      # ✅ Basic structure
│   ├── requirements.txt                # ✅ Dependencies defined
│   ├── main.py                         # ✅ FastAPI service with tool endpoints
│   ├── config.py                       # ✅ Configuration management
│   ├── PHASE2_SUMMARY.md              # ✅ Implementation documentation
│   │
│   ├── agents/                         # ✅ PHASE 1 COMPLETE
│   │   ├── __init__.py                 # ✅ Package setup
│   │   ├── base.py                     # ✅ Abstract agent base class
│   │   └── chat.py                     # ✅ Chat agent implementation
│   │
│   ├── core/                           # ✅ PHASE 1 COMPLETE  
│   │   ├── __init__.py                 # ✅ Package setup
│   │   ├── session.py                  # ✅ Session management
│   │   └── llm_client.py              # ✅ LLM proxy integration
│   │
│   ├── tools/                          # ✅ PHASE 2 COMPLETE (12 modules)
│   │   ├── __init__.py                 # ✅ Comprehensive exports
│   │   ├── README.md                   # ✅ Tool system documentation
│   │   ├── base.py                     # ✅ Core interfaces and validation
│   │   ├── registry.py                 # ✅ Tool discovery and management
│   │   ├── executor.py                 # ✅ Execution engine with retry/caching
│   │   ├── formatter.py                # ✅ Result formatting (4 formats)
│   │   ├── metrics.py                  # ✅ Analytics and monitoring
│   │   ├── auth.py                     # ✅ RBAC and audit logging
│   │   ├── streaming.py                # ✅ Real-time progress updates
│   │   ├── docs.py                     # ✅ Auto-documentation generation
│   │   ├── mcp_client.py              # ✅ MCP protocol integration
│   │   ├── email.py                    # ✅ Email tools (search/summarize/draft)
│   │   ├── search.py                   # ✅ Web search tools
│   │   └── data.py                     # ✅ Database and file tools
│   │
│   └── guardrails/                     # 🔄 PLANNED FOR PHASE 4
│       ├── __init__.py                 # [ ] Package setup
│       ├── input.py                    # [ ] Input validation
│       ├── output.py                   # [ ] Output safety
│       └── audit.py                    # [ ] Compliance logging
│
├── polyllama/ui/app/api/agent/         # 🔄 PENDING FROM PHASE 1
│   ├── chat/                           # [ ] Agent chat endpoint
│   │   └── route.ts                    # [ ] Next.js streaming integration
│   ├── status/                         # [ ] Agent status endpoint  
│   │   └── route.ts                    # [ ] Health and metrics
│   └── sessions/                       # [ ] Session management
│       └── route.ts                    # [ ] Session CRUD operations
│
└── tests/agent_controller/             # ✅ COMPREHENSIVE TESTING
    └── tools/                          # ✅ Tool system tests
        ├── test_base.py               # ✅ Base interface unit tests
        ├── test_registry.py           # ✅ Registry functionality tests
        └── test_email_integration.py  # ✅ Email tool integration tests
```

**Legend:**
- ✅ = Fully implemented and tested
- 🔄 = Planned for future phases  
- [ ] = Not yet implemented

## LLM Client Integration

```python
# stack/agent-controller/core/llm_client.py
class LLMProxyClient:
    """Client for LLM proxy (litellm) that supports multiple providers"""
    
    def __init__(self, base_url: str = "http://llm-proxy:11435"):
        self.base_url = base_url
    
    async def stream(self, prompt: str, model: str = None):
        """Stream response from LLM"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model or "default",
                "messages": [{"role": "user", "content": prompt}],
                "stream": True
            }
            
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                async for line in response.content:
                    if line:
                        chunk = json.loads(line.decode('utf-8').strip('data: '))
                        if content := chunk.get('choices', [{}])[0].get('delta', {}).get('content'):
                            yield content
```

## Docker Compose Addition

```yaml
# Add to builder/docker-compose.yml.j2
agent-controller:
  build:
    context: ./stack/agent-controller
  container_name: agent-controller
  ports:
    - "11436:11436"  # Internal only
  environment:
    - LLM_PROXY_URL=http://llm-proxy:11435
    - REDIS_URL=redis://redis:6379
  networks:
    - polyllama-network
  depends_on:
    - llm-proxy
    - redis
```

## Testing Strategy

1. **Unit Tests**
   - Tool wrapper functionality
   - Agent state management
   - Input/output validation

2. **Integration Tests**
   - End-to-end agent flows
   - Multi-agent coordination
   - Streaming response handling

3. **Load Tests**
   - Concurrent session handling
   - Token usage optimization
   - Response time benchmarks

4. **Security Tests**
   - Input injection attempts
   - Authentication bypass attempts
   - Data leakage prevention

## Deployment Considerations

- Configure resource limits for agent service
- Set up monitoring for token usage and costs
- Implement rate limiting per user/session
- Add health checks for all components
- Configure log aggregation for debugging

## Key Streaming Patterns

### 1. Simple Pass-through (Chat Routes)
```typescript
// When proxying without server-side processing
if (response.ok && response.body) {
  return new Response(response.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    }
  })
}
```

### 2. Transform Stream (Agent Routes)
```typescript
// When server needs to process/transform the stream
const stream = new TransformStream({
  async transform(chunk, controller) {
    // Parse agent response, format for UI
    const data = JSON.parse(chunk)
    const formatted = formatAgentResponse(data)
    controller.enqueue(new TextEncoder().encode(formatted))
  }
})
const transformedStream = response.body.pipeThrough(stream)
return new Response(transformedStream, { headers: streamHeaders })
```

## OpenAI Format Consistency

The system uses standard OpenAI streaming format throughout for compatibility:

### Streaming Format
All streaming responses follow OpenAI's Server-Sent Events (SSE) format:
```
data: {"choices": [{"delta": {...}, "finish_reason": null, "index": 0}]}
data: {"choices": [{"delta": {...}, "finish_reason": null, "index": 0}]}
data: {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]}
data: [DONE]
```

### Content Streaming
Regular assistant content is streamed as:
```json
{"choices": [{"delta": {"content": "Hello, how can I help?"}, "finish_reason": null, "index": 0}]}
```

### Tool Call Streaming
Tool calls are streamed in OpenAI format:
1. Initial tool call (when detected):
```json
{"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_123", "type": "function", "function": {"name": "search_web", "arguments": ""}}]}, "finish_reason": null, "index": 0}]}
```

2. Complete tool call (with arguments):
```json
{"choices": [{"delta": {"tool_calls": [{"id": "call_123", "type": "function", "function": {"name": "search_web", "arguments": "{\"query\": \"weather\"}"}}]}, "finish_reason": null, "index": 0}]}
```

### Tool Results
Tool results are currently streamed as content (not as separate tool messages):
```json
{"choices": [{"delta": {"content": "\n[Tool: search_web]\nFound 5 results for weather...\n"}, "finish_reason": null, "index": 0}]}
```

### Frontend Handling
The frontend (`chatUtils.ts`) parses OpenAI format and:
- Displays content chunks immediately
- Shows "Preparing to call tool..." when tool calls start
- Updates to show full tool details when arguments are complete
- Displays tool results as part of the assistant's message content

**Note**: Tool results appearing as raw JSON arrays (e.g., `[{'type': 'text', 'text': '...'}]`) indicate the MCP bridge is returning structured responses that need to be properly formatted before display.

## Security Considerations

- All agent→LLM calls use LLM proxy with proper authentication
- Agent controller never exposes tools directly to clients
- Session data encrypted at rest
- PII masking before tool execution
- Rate limiting on agent endpoints
- Audit trail for all agent actions

## Monitoring & Observability

- OpenTelemetry integration for distributed tracing
- Prometheus metrics for:
  - Agent response times
  - Tool execution counts
  - Token usage per session
  - Error rates by agent type
- Structured logging with correlation IDs
- Real-time dashboards for agent performance

## MCP Server Implementation - Critical Notes

### Streamable HTTP Proxy Compatibility

**CRITICAL: Single-Event SSE Format for MCP Client Compatibility**

The MCP server proxy (`stack/llm-proxy/mcp-server/server_streamable_http.js`) implements a **single-event SSE streaming format** that is essential for compatibility with MCP inspection tools like `mcpinspection v0.16.1`.

**Key Implementation Details:**
```javascript
// CORRECT: Single event after tool completion
// Execute tool first, then send only final result
const content = await executeTool(name, args || {});
const finalEvent = {
  jsonrpc: '2.0',
  id,
  result: { content }
};
res.write(`data: ${JSON.stringify(finalEvent)}\n\n`);
res.end();
```

**DO NOT use multi-event streaming:**
```javascript
// INCORRECT: Multi-event format causes mcpinspection to hang
res.write(`data: ${JSON.stringify(startEvent)}\n\n`);  // Start event
// ... tool execution ...
res.write(`data: ${JSON.stringify(resultEvent)}\n\n`); // Result event  
res.write(`data: ${JSON.stringify(completeEvent)}\n\n`); // Complete event
```

**Why This Matters:**
- MCP inspection tools expect a single, final response after tool completion
- Multi-event streams cause clients to hang after receiving the first event
- The single-event format ensures proper tool execution waiting and result delivery
- This pattern is required for `mcpinspection`, MCP IDEs, and other MCP-compliant clients

**Testing Commands:**
```bash
# Test with curl (should work with both formats)
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"jsonrpc": "2.0", "id": "test", "method": "tools/call", "params": {"name": "github__search_users", "arguments": {"q": "username"}}}' \
  -N

# Test with mcpinspection (requires single-event format)
# Should receive complete tool results, not hang after first event
```

**Related Files:**
- `stack/llm-proxy/mcp-server/server_streamable_http.js` - Main implementation
- `mcp-config.json` - Upstream MCP server configuration

## MCP Configuration Management

**CRITICAL: Do NOT modify mcp-config.json unless explicitly requested**

The `mcp-config.json` file contains user-specific MCP server configurations including:
- Personal AI servers (e.g., personal-ai connecting to localhost:8084/sse)
- API keys and authentication tokens
- Custom server endpoints and configurations

**Guidelines:**
- Never remove or modify existing server configurations during debugging
- If troubleshooting requires temporary changes, restore the original configuration immediately
- User configurations should be preserved across all development sessions
- Always check with the user before making any changes to this file

## Do NOT

- Modify existing Nginx configurations
- Expose agent tools as public APIs
- Allow client-side tool execution
- Bypass API-KEY authentication
- Create agent-specific Ollama instances
- **Use multi-event SSE streaming in MCP server proxy** - breaks MCP client compatibility
- **Modify mcp-config.json without explicit user permission** - contains personal configurations
