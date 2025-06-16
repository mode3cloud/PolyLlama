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
- `/ui/*` - Next.js web UI for monitoring and chat interface

**API Communication Patterns:**
1. **Ollama API Access** (Dashboard/Monitoring):
   - UI components use `/api/*` endpoints (e.g., `/api/models`, `/api/generate`)
   - These are routed by Nginx to the appropriate Ollama instance
   - Example: `fetch('/api/models')` from the UI hits `localhost:11434/api/models`

2. **LLM Proxy Access** (Chat Interface):
   - Chat UI uses Next.js API routes: `/ui/api/chat/*`
   - Next.js server-side routes proxy to `http://llm-proxy:11435`
   - This enables multi-provider support (OpenAI, Anthropic, etc.) via litellm
   - Example: `fetch('/ui/api/chat/models')` → Next.js API → `http://llm-proxy:11435/api/models`

**Key Design Principles:**
- Never make direct calls to Docker service names from client-side code
- All inter-service communication happens server-side
- The UI at `/ui` can call both `/api/*` (Ollama) and `/ui/api/*` (LLM proxy) endpoints
- LLM proxy may internally call back to Ollama via `localhost:11434/api/*`

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