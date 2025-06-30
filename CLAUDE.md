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

# PolyLlama Multi-Agent Implementation Plan

## Overview

This document provides a comprehensive implementation plan for adding multi-agent capabilities to PolyLlama while preserving the existing multi-instance Ollama architecture, security patterns, and routing logic.

## Architecture Overview

### Core Principles

- **No Disruption**: Maintain existing Nginx/Lua routing logic unchanged
- **Server-Side Only**: All agent/tool operations must be server-side (no browser-based tool calls)
- **Security First**: Preserve API-KEY and JWT/OAuth patterns on all endpoints
- **Incremental**: Build single-agent flows before multi-agent orchestration
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
|   - Implements Aggregator Agent with planning capabilities                          |
|   - Streaming support: yields partial LLM or agent output back to API               |
|   - Orchestrates workflow:                                                          |
|        a) Plan/Reason (CoT, ReACT, etc)                                            |
|        b) Decide which sub-agent/tool to call                                      |
|        c) Invoke LLM via LLM Proxy (litellm)                                       |
|        d) Invoke MCP sub-agents as needed                                          |
|        e) Combine/generate results                                                 |
+------------------------+---------------+---------------+-----------------------------+
                         |               |               |
          [Sub-Agent: Search]   [Sub-Agent: Local Data]   [Sub-Agent: Cloud/API]
           - Calls MCP search      - Calls DB/file/API       - Calls cloud API, etc.
           - Returns results       - Returns results         - Returns results
                         |               |               |
                         +-------+-------+-------+-------+
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

## Implementation Phases

### Phase 1: Single-Agent Foundation

1. **Create Agent Controller Service**
   ```python
   # stack/agent-controller/main.py
   from fastapi import FastAPI
   from fastapi.responses import StreamingResponse
   
   app = FastAPI()
   
   @app.post("/agent/chat")
   async def agent_chat(request: AgentRequest):
       async def generate():
           async for chunk in agent.process(request):
               yield f"data: {json.dumps(chunk)}\n\n"
       return StreamingResponse(generate(), media_type="text/event-stream")
   ```

2. **Add Next.js API Routes**
   ```typescript
   // app/api/agent/chat/route.ts
   export async function POST(req: Request) {
     const { userPrompt, sessionId } = await req.json()
     
     // Stream from agent controller to client
     const response = await fetch('http://agent-controller:11436/agent/chat', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({ userPrompt, sessionId })
     })
     
     // Pass through the stream
     return new Response(response.body, {
       headers: {
         'Content-Type': 'text/event-stream',
         'Cache-Control': 'no-cache',
         'Connection': 'keep-alive',
       }
     })
   }
   ```

3. **Implement Core Agent Loop**
   ```python
   class Agent:
       async def process(self, request: AgentRequest):
           # Load session state
           session = await self.load_session(request.session_id)
           
           # Compose prompt with instructions + context
           prompt = self.build_prompt(session, request.user_prompt)
           
           # Stream reasoning steps
           yield {"type": "thinking", "content": "Analyzing request..."}
           
           # Call LLM via proxy
           async for chunk in self.llm_client.stream(prompt):
               yield {"type": "llm_output", "content": chunk}
           
           # Parse for tool requirements
           if tools_needed := self.parse_tools(response):
               for tool in tools_needed:
                   result = await self.execute_tool(tool)
                   yield {"type": "tool_result", "tool": tool.name, "result": result}
           
           # Save session state
           await self.save_session(session)
   ```

### Phase 2: Tool Integration

1. **Standard Tool Interface**
   ```python
   # stack/agent-controller/tools/base.py
   from abc import ABC, abstractmethod
   
   class Tool(ABC):
       @property
       @abstractmethod
       def name(self) -> str:
           pass
       
       @property
       @abstractmethod
       def description(self) -> str:
           pass
       
       @abstractmethod
       async def execute(self, args: dict) -> dict:
           pass
   ```

2. **Example MCP Tool Wrapper**
   ```python
   # stack/agent-controller/tools/email.py
   class EmailSearchTool(Tool):
       name = "email_search"
       description = "Search through email messages"
       
       def __init__(self, mcp_client):
           self.mcp = mcp_client
       
       async def execute(self, args: dict) -> dict:
           query = args.get("query", "")
           results = await self.mcp.search_emails(query)
           return {
               "status": "success",
               "results": results,
               "count": len(results)
           }
   ```

3. **Tool Registry**
   ```python
   # stack/agent-controller/tools/registry.py
   class ToolRegistry:
       def __init__(self):
           self.tools = {}
       
       def register(self, tool: Tool):
           self.tools[tool.name] = tool
       
       def get_tool(self, name: str) -> Tool:
           return self.tools.get(name)
       
       def list_tools(self) -> List[dict]:
           return [
               {"name": t.name, "description": t.description}
               for t in self.tools.values()
           ]
   ```

### Phase 3: Multi-Agent Orchestration

1. **Agent Types**
   ```python
   # stack/agent-controller/agents/
   class ManagerAgent(Agent):
       """Delegates to specialist agents"""
       async def delegate(self, task, specialist):
           # Hand off control to specialist
           pass
   
   class ResearchAgent(Agent):
       """Specialized in research tasks"""
       tools = ["search", "summarize", "extract"]
   
   class DataAgent(Agent):
       """Specialized in data analysis"""
       tools = ["query", "analyze", "visualize"]
   ```

2. **Orchestration Patterns**
   - **Manager Pattern**: Top-level agent delegates to specialists
   - **Pipeline Pattern**: Sequential agent processing
   - **Consensus Pattern**: Multiple agents vote on output
   - **Handoff Pattern**: Agents transfer control based on domain

### Phase 4: Guardrails & Safety

1. **Input Validation**
   ```python
   class InputValidator:
       async def validate(self, input_text: str):
           # Content filtering
           if await self.contains_harmful_content(input_text):
               raise ValidationError("Harmful content detected")
           
           # PII detection
           pii_entities = await self.detect_pii(input_text)
           if pii_entities:
               input_text = self.mask_pii(input_text, pii_entities)
           
           return input_text
   ```

2. **Output Safety**
   ```python
   class OutputValidator:
       async def validate(self, output: str, context: dict):
           # Check for sensitive information
           # Validate against business rules
           # Flag high-risk responses
           pass
   ```

3. **Audit Logging**
   ```python
   class AuditLogger:
       async def log_action(self, session_id: str, action: dict):
           # Log to persistent storage
           # Include: timestamp, user, action, tools used, outcome
           pass
   ```

## File Structure

```
stack/
├── agent-controller/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── config.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── manager.py
│   │   ├── research.py
│   │   └── data.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── session.py
│   │   ├── prompts.py
│   │   └── llm_client.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── email.py
│   │   ├── search.py
│   │   └── data.py
│   └── guardrails/
│       ├── __init__.py
│       ├── input.py
│       ├── output.py
│       └── audit.py
└── polyllama/ui/app/api/agent/
    ├── chat/
    │   └── route.ts
    ├── status/
    │   └── route.ts
    └── sessions/
        └── route.ts
```

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

## Do NOT

- Modify existing Nginx configurations
- Expose agent tools as public APIs
- Allow client-side tool execution
- Bypass API-KEY authentication
- Create agent-specific Ollama instances
