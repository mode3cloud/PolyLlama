# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
docker-compose -f builder/built/docker-compose.yml up -d
docker-compose -f builder/built/docker-compose.yml logs polyllama1
docker-compose -f builder/built/docker-compose.yml ps
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
- We use pnpm NOT npm

## Agent Layer Implementation Plan

### Overview

This section outlines the incremental approach to adding agent capabilities (tool use, orchestration, guardrails) to PolyLlama while preserving the existing multi-instance Ollama architecture and security patterns.

### Core Principles

- **No Disruption**: Maintain existing Nginx/Lua routing logic unchanged
- **Server-Side Only**: All agent/tool operations must be server-side (no browser-based tool calls)
- **Security First**: Preserve API-KEY and JWT/OAuth patterns on all endpoints
- **Incremental**: Build single-agent flows before multi-agent orchestration

### Architecture Components

#### 1. Agent Controller Service (NEW)

Deploy as a Python FastAPI service alongside existing services:

- Location: `stack/agent-controller/`
- Port: 11436 (internal only)
- Responsibilities:
  - Orchestrate LLM workflows using PolyLlama backend
  - Manage agent sessions and conversation state
  - Interface with MCP tools and external services
  - Handle turn-taking and context management

#### 2. Tool Registry (NEW)

Standardized tool interface for all integrations:

- Each MCP/external service wrapped as Python callable
- Consistent interface: `def tool(args: dict) -> dict`
- Central registry in `agent_controller/tools/`
- Tools invoked by agent code, not LLM directly

#### 3. Integration Pattern

```text
[Browser] → [Next.js /ui/api/agent/*] → [Agent Controller :11436] → [Ollama via :11434/api/*]
                                              ↓
                                         [MCP Tools/Services]
```

### Implementation Phases

#### Phase 1: Single-Agent Foundation

1. Create agent controller service with basic session management
2. Add Next.js API routes:
   - `/ui/api/agent/chat` - Agent-powered chat
   - `/ui/api/agent/status` - Session status
3. Implement core agent loop:

   ```python
   # Pseudocode for agent step
   def agent_step(session_id, user_input):
       # Load session state
       # Compose prompt with instructions + context
       # Call LLM via localhost:11434/api/* with API-KEY
       # Parse for tool requirements
       # Execute tools if needed
       # Return response or request user input
   ```

#### Phase 2: Tool Integration

1. Wrap existing MCP tools with standard interface
2. Create tool metadata registry (name, description, parameters)
3. Implement tool detection in LLM responses
4. Add tool result injection back into agent context

#### Phase 3: Multi-Agent Orchestration

1. Extend controller for multiple agent instances per session
2. Implement agent patterns:
   - **Manager Pattern**: Top-level agent delegates to specialists
   - **Handoff Pattern**: Agents transfer control based on domain
3. Add inter-agent communication via shared session state

#### Phase 4: Guardrails & Safety

1. Input validation middleware:
   - Content filtering (regex, classifiers)
   - PII detection and masking
2. Output safety checks:
   - Response validation
   - High-risk action confirmation
3. Audit logging for all agent actions

### Technical Integration Details

#### LLM Communication

- All agent→LLM calls use existing `/api/*` endpoints
- Always include API-KEY header for Ollama access
- Maintain model routing through existing Lua logic
- No direct Ollama container access

#### Session Management

- Store state in Redis or PostgreSQL (not in-memory)
- Session schema:

  ```json
  {
    "session_id": "uuid",
    "agent_type": "chat|workflow|email",
    "context": [...],
    "tools_used": [...],
    "state": "active|paused|complete"
  }
  ```

#### Tool API Standards

```python
# Example tool wrapper
class EmailSearchTool:
    def __init__(self, mcp_client):
        self.mcp = mcp_client
        
    def search(self, args: dict) -> dict:
        # Validate args
        # Call MCP email service
        # Format response for agent
        return {"status": "success", "results": [...]}
```

### File Structure Additions

```text
stack/
├── agent-controller/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── controller.py
│   │   ├── session.py
│   │   └── prompts.py
│   └── tools/
│       ├── __init__.py
│       ├── registry.py
│       ├── email.py
│       └── search.py
└── polyllama/ui/app/api/agent/
    ├── chat/
    │   └── route.ts
    └── status/
        └── route.ts
```

### Testing Strategy

- Unit tests for each tool wrapper
- Integration tests for agent flows
- Load tests for concurrent sessions
- Security tests for input validation

### Deployment Considerations

- Add agent-controller to docker-compose template
- Configure service discovery for MCP access
- Set resource limits for agent service
- Monitor token usage and costs

### Do NOT

- Modify existing Nginx configurations
- Expose agent tools as public APIs
- Allow client-side tool execution
- Bypass API-KEY authentication
- Create agent-specific Ollama instances
