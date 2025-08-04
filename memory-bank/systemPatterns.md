# PolyLlama System Architecture & Patterns

## Core Architecture Components

### 1. Hardware Detection & Configuration Generation
**Pattern**: Dynamic Infrastructure as Code
- **Entry Point**: `polyllama.sh` → `builder/cli.py`
- **Detection**: `builder/detector.py` uses `nvidia-smi` for GPU discovery
- **Generation**: `builder/generator.py` renders Jinja2 templates
- **Output**: `builder/built/docker-compose.yml` and `builder/built/nginx.conf`

**Key Design Principle**: Hardware drives configuration, not vice versa

### 2. Request Routing Architecture
**Pattern**: Intelligent Proxy with State Management
- **Entry Point**: Nginx router at `:11434` (`stack/polyllama/`)
- **Intelligence**: Lua-based routing (`model_router.lua`)
- **State Management**: Shared memory for model-to-instance mappings
- **Load Balancing**: Least-loaded instance assignment for new models

**Routing Hierarchy**:
1. Existing running model → Route to current instance
2. Cached mapping → Use stored model-to-instance mapping
3. Least loaded assignment → Assign to instance with fewest models
4. Loading locks → Prevent duplicate loading across instances

### 3. Service Communication Patterns
**Pattern**: Layered Proxy Architecture

```
Client → Nginx (:11434) → Ollama Instance (polyllama1, polyllama2...)
       ↘ Next.js UI (:3000) ← LLM Proxy (:11435)
```

**Critical Rule**: Client browsers cannot access Docker service names directly
- `/api/*` → Direct Ollama routing via Nginx
- `/ui/api/*` → Next.js API routes → LLM Proxy → Back to Ollama if needed

### 4. Template System Pattern
**Custom Renderer** (not Jinja2 for loops):
- `{% for instance in ollama_instances %}` - Loop through instances
- `{{ instance.property }}` - Variable substitution
- `{% if instance.gpu_indices %}` - Conditional rendering

**Template Files**:
- `docker-compose.yml.j2` → Service definitions
- `nginx.conf.j2` → Routing configuration

### 5. Instance Naming Convention
**Pattern**: Consistent Service Naming
- Services: `polyllama1`, `polyllama2`, `polyllama3...` (NOT `ollama1`)
- Environment variable propagation: `OLLAMA_INSTANCE_COUNT`
- Lua access: `get_instance_count()` function

### 6. Mixed Hardware Support Pattern
**CPU Routing Modes**:
- `prefer_gpu` (default): GPU instances preferred, CPU as fallback
- `balanced`: Equal treatment of all instances
- `gpu_only`: Never route to CPU instances automatically

**Environment Variables**:
- `POLYLLAMA_CPU_INSTANCES`: Number of CPU instances (default: 0)
- `POLYLLAMA_MIXED_MODE`: Enable mixed deployment (default: false)
- `POLYLLAMA_CPU_ROUTING_MODE`: Routing preference

## Key Design Patterns

### 1. State Propagation Pattern
Instance count flows through system:
1. Set in `docker-compose.yml` environment
2. Read by nginx `init_by_lua_block` 
3. Stored in shared memory (`env_vars`)
4. Accessed by routing logic
5. Exposed via UI endpoint `/api/polyllama/instance-count`

### 2. Security Layer Pattern
**API Key Protection**: All `/api/*` endpoints protected except internal UI endpoints
**Headers Accepted**: `api-key`, `x-api-key`, `Authorization: Bearer`
**Implementation**: Nginx Lua `access_by_lua_block`

### 3. Streaming Response Patterns
**Simple Pass-through**: Direct proxy without processing
**Transform Stream**: Server-side processing with TransformStream
**Critical**: Never call `response.body.getReader()` before `pipeThrough()`

### 4. Package Management Pattern
- **JavaScript/UI**: pnpm (NOT npm)
- **Python**: uv dependency management
- **Testing**: pytest (NOT local scripts)

## Service Dependencies

### Core Services
1. **Router** (`stack/polyllama/`) - Nginx + Lua routing
2. **Ollama Instances** (`stack/ollama/`) - GPU-assigned model runners
3. **LLM Proxy** (`stack/llm-proxy/`) - Multi-provider abstraction
4. **Next.js UI** (`stack/polyllama/ui/`) - Web interface
5. **MCP Server** (`stack/llm-proxy/mcp-server/`) - Tool integration

### Optional Services
- **Open WebUI** (`stack/open-webui/`) - Alternative interface
- **Olah** (`stack/olah/`) - Additional model management

## Critical Implementation Notes

### MCP Server Compatibility
**CRITICAL**: Single-event SSE format required for MCP client compatibility
- Execute tool first, then send single final result
- DO NOT use multi-event streaming (breaks mcpinspection tools)
- File: `stack/llm-proxy/mcp-server/server.py`

### Configuration Management
**DO NOT modify `mcp-config.json`** without explicit user permission
- Contains user-specific MCP server configurations
- Includes personal API keys and endpoints
- Preserve across all development sessions