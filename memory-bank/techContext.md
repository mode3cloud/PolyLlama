# PolyLlama Technical Context

## Technology Stack

### Core Infrastructure
- **Containerization**: Docker & Docker Compose
- **Orchestration**: Custom Python CLI with hardware detection
- **Load Balancing**: Nginx with custom Lua scripting
- **GPU Management**: CUDA via `nvidia-smi` detection

### Backend Services
- **Python 3.10+**: Core orchestration and proxy services
- **FastAPI**: LLM proxy service with uvicorn ASGI server
- **LiteLLM 1.61.15**: Multi-provider LLM abstraction
- **Redis**: Session persistence and caching
- **Neo4j**: Knowledge graph for advanced features

### Frontend
- **Next.js**: React-based web UI
- **TypeScript**: Type-safe client development
- **Tailwind CSS**: Utility-first styling
- **Server-Side Events (SSE)**: Real-time streaming

### Package Management
- **Python**: `uv` (modern pip replacement)
- **JavaScript**: `pnpm` (performance-focused npm alternative)
- **Dependencies**: Defined in `pyproject.toml` and `package.json`

### Testing Framework
- **Python**: `pytest` with async support
- **Coverage**: pytest-cov with HTML/XML reporting
- **Integration**: Test containers and mock services
- **Continuous Integration**: GitHub Actions

## Development Environment Setup

### Prerequisites
```bash
# System requirements
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+ (for UI development)
- NVIDIA drivers (for GPU support)
```

### Dependency Installation
```bash
# Python dependencies
uv sync

# Frontend dependencies (in stack/polyllama/ui/)
pnpm install
```

### Common Commands
```bash
# Launch system with hardware detection
./polyllama.sh

# Development mode with debug output
./polyllama.sh --debug

# Run complete test suite
./tests/run_tests.sh

# Run specific tests
uv run pytest tests/test_generation.py -v

# Manual template generation
python3 builder/generate_compose.py '{"gpu_groups":[...]}'
```

## Configuration Management

### Environment Variables
- `POLYLLAMA_API_KEY`: Protect API endpoints
- `POLYLLAMA_CPU_INSTANCES`: Number of CPU instances (default: 0)
- `POLYLLAMA_MIXED_MODE`: Enable mixed GPU+CPU (default: false)
- `POLYLLAMA_CPU_ROUTING_MODE`: prefer_gpu|balanced|gpu_only
- `OLLAMA_INSTANCE_COUNT`: Runtime instance count (auto-set)

### Configuration Files
- `.env`: Environment variables (created from `.env.example`)
- `mcp-config.json`: MCP server configurations (user-specific)
- `builder/built/`: Generated configurations (auto-created)

## API Architecture

### Endpoint Structure
```
:11434 (Public Interface)
├── /api/* → Ollama instances (protected by API key)
├── /ui/* → Next.js UI (stripped prefix)
└── Internal endpoints:
    ├── /api/polyllama/* (UI monitoring endpoints)
    └── /ui/api/* (Next.js API routes)
```

### Service Communication
```
Browser → :11434/ui/api/* → Next.js → :11435 (LLM Proxy)
Browser → :11434/api/* → Nginx → polyllama1/2/3... (Ollama)
```

### Authentication Patterns
- **API Endpoints**: API key validation (api-key, x-api-key, Authorization headers)
- **UI Features**: JWT tokens via OAuth
- **Internal**: Service-to-service with API key passthrough

## Streaming & Real-time Features

### OpenAI Format Consistency
All streaming follows OpenAI Server-Sent Events format:
```json
data: {"choices": [{"delta": {"content": "..."}, "finish_reason": null, "index": 0}]}
data: [DONE]
```

### Tool Call Streaming
- Tool preparation: Shows "Preparing to call tool..."
- Tool execution: Displays tool name and arguments
- Tool results: Integrated into assistant responses
- Error handling: Tool-specific error display

### MCP Integration
- **Protocol**: Model Context Protocol for tool integration
- **Server**: Node.js streamable HTTP proxy
- **Format**: Single-event SSE (critical for client compatibility)
- **Tools**: GitHub, personal assistant, browser automation, etc.

## Security Implementation

### API Protection
- Nginx Lua-based API key validation
- Header sanitization in logs
- CORS configuration for UI access
- JWT authentication for advanced features

### Data Protection
- Environment variable isolation
- Configuration file encryption
- Session data protection
- Audit logging for tool executions

## Performance Characteristics

### Hardware Optimization
- Automatic GPU detection and grouping
- CUDA_VISIBLE_DEVICES per instance
- Memory-efficient model loading
- Instance availability checking

### Load Balancing
- Least-loaded instance selection
- Model-to-instance affinity
- Loading locks prevent duplication
- Shared memory state management

### Monitoring
- GPU metrics collection
- Instance health checks
- Model loading status
- Request routing analytics

## Development Constraints

### Required Patterns
- Server-side only Docker service communication
- API key enforcement on all public endpoints
- Single-event MCP streaming format
- Preserve user MCP configurations

### Forbidden Patterns
- Client-side Docker service access
- Multi-event MCP streaming
- Bypassing API key protection
- Modifying user MCP configs without permission