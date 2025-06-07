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
4. JavaScript UI reads via `/api/ui/instance-count` endpoint

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
- Examine shared memory state via `/api/ui/model-mappings`
- Verify `OLLAMA_INSTANCE_COUNT` propagation

### Service Communication
- Ensure all `polyllamaX` services can resolve each other via Docker networks
- Check that nginx upstream pool matches actual running services
- Verify GPU assignments in container environment variables

## Development Guidelines
- We use pnpm NOT npm