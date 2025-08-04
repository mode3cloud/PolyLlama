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
- We use **uv** for Python dependency management

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


