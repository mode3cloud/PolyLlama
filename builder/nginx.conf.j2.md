# Nginx Endpoints Configuration Table

## Authentication

PolyLlama implements API key authentication for all API endpoints:

### Implementation Details

1. **All API Endpoints** (`/api/*` including `/api/polyllama/*`):
   - Protected by API key authentication
   - Uses `Authorization: Bearer <API_KEY>` header format
   - Environment variable `POLYLLAMA_API_KEY` stores the required key
   - When no key is set, authentication is disabled (open access)
   - Authentication check implemented via Lua `check_api_auth()` function
   - Includes both Ollama-compatible endpoints and PolyLlama management endpoints

2. **UI Access** (`/ui/*`):
   - Proxied to Next.js application on port 3000
   - Authentication handled by Next.js (OAuth/JWT)
   - Next.js server-side API routes add API key when calling nginx
   - API keys never exposed to browser/client-side code

### Authentication Flow

1. **External API Requests**:
   - Client includes API key in Authorization header: `Authorization: Bearer your-api-key`
   - Nginx validates the key in `access_by_lua_block` or `rewrite_by_lua_block`
   - Invalid/missing keys return 401 Unauthorized with JSON error response
   - Valid requests are proxied with model-aware routing

2. **UI Server-Side Requests**:
   - Next.js API routes add API key when calling nginx endpoints
   - API key stored server-side in environment variables
   - Client-side code never sees or handles API keys

### Configuration

To enable API key authentication:

```bash
# Set the API key in your .env file or environment
export POLYLLAMA_API_KEY="your-secure-api-key"

# Launch PolyLlama
./polyllama.sh
```

When `POLYLLAMA_API_KEY` is not set or empty, authentication is disabled and all `/api/*` endpoints are open.

## Core Ollama API Endpoints (PolyLlama overrides with smart routing logic)

| Endpoint          | Method | Purpose               | Routing Logic                                           | Special Features                                   |
| ----------------- | ------ | --------------------- | ------------------------------------------------------- | -------------------------------------------------- |
| `/api/generate`   | POST   | Text generation       | Model-aware routing to specific instances               | Context length management, model loading detection |
| `/api/chat`       | POST   | Chat completions      | Model-aware routing to specific instances               | Context length management, model loading detection |
| `/api/embeddings` | POST   | Generate embeddings   | Model-aware routing to specific instances               | Context length management, model loading detection |
| `/api/show`       | POST   | Show model details    | Load-balanced to any instance                           | Logs request context                               |
| `/api/load`       | POST   | Load models           | Assigns to least loaded instance or target              | Supports X-Target-Instance header                  |
| `/api/tags`       | GET    | List available models | Custom aggregation from all instances                   | Returns sorted models from all instances           |
| `/api/ps`         | GET    | List running models   | Merged response from all instances OR specific instance | Supports X-Target-Instance header                  |
| `/api/version`    | GET    | Get Ollama version    | Load-balanced                                           | Returns version from any instance                  |

## Custom Polyllama Management Endpoints

| Endpoint                         | Method | Purpose                        | Response Format | Description                                     |
| -------------------------------- | ------ | ------------------------------ | --------------- | ----------------------------------------------- |
| `/api/polyllama/instance-status` | GET    | Check instance health          | JSON            | Returns online/offline status for all instances |
| `/api/polyllama/instance-count`  | GET    | Get total instance count       | JSON            | Returns configured number of instances          |
| `/api/polyllama/gpu-config`      | GET    | Get GPU configuration          | JSON            | Returns GPU groups and instance mappings        |
| `/api/polyllama/gpu-metrics`     | GET    | Get GPU/CPU metrics            | JSON            | Real-time GPU utilization and CPU metrics       |
| `/api/polyllama/running-models`  | GET    | Get running models             | JSON            | Models currently loaded across all instances    |
| `/api/polyllama/model-mappings`  | GET    | Get model-to-instance mappings | JSON            | Current routing mappings                        |
| `/api/polyllama/model-details`   | POST   | Get detailed model info        | JSON            | Extended model information                      |
| `/api/polyllama/search-models`   | GET    | Search Ollama.com models       | JSON            | Search available models from registry           |
| `/api/polyllama/pull-model`      | POST   | Pull model from registry       | JSON            | Initiate model download                         |
| `/api/polyllama/pull-status`     | GET    | Check pull progress            | JSON            | Status of ongoing model pulls                   |
| `/api/polyllama/pull-statuses`   | GET    | Get all pull statuses          | JSON            | All active pull operations                      |

## Context Management Endpoints

| Endpoint                       | Method | Purpose                           | Body Format                          | Description                          |
| ------------------------------ | ------ | --------------------------------- | ------------------------------------ | ------------------------------------ |
| `/api/polyllama/get-contexts`  | GET    | Get stored context lengths        | N/A                                  | Returns context sizes for all models |
| `/api/polyllama/store-context` | POST   | Store context length              | `{"model": "name", "num_ctx": 4096}` | Store context size for a model       |
| `/api/polyllama/sync-contexts` | POST   | Sync contexts from running models | N/A                                  | Extract and store context sizes      |

## Maintenance Endpoints

| Endpoint                          | Method | Purpose                 | Description                               |
| --------------------------------- | ------ | ----------------------- | ----------------------------------------- |
| `/api/polyllama/clean-mappings`   | POST   | Clean stale mappings    | Remove mappings for non-running models    |
| `/api/polyllama/duplicate-models` | GET    | Detect duplicate models | Find models running on multiple instances |


## UI and Static Content

| Path  | Purpose             | Proxy Target            | Notes                     |
| ----- | ------------------- | ----------------------- | ------------------------- |
| `/`   | Root redirect       | Redirects to `/ui/`     | 301 redirect              |
| `/ui` | Next.js application | `http://127.0.0.1:3000` | WebSocket support for HMR |

## Special Headers

| Header                | Used By                                      | Purpose                                  |
| --------------------- | -------------------------------------------- | ---------------------------------------- |
| `X-Target-Instance`   | `/api/load`, `/api/ps`, generation endpoints | Route to specific instance               |
| `X-Served-By`         | All endpoints                                | Indicates which instance handled request |
| `X-Ollama-First-Load` | Generation endpoints                         | Indicates first load of a model          |

## Routing Logic Details

### Model-Aware Endpoints (`/api/generate`, `/api/chat`, `/api/embeddings`)

1. **Request Processing**: Extract model name from request body
2. **Running Check**: Check if model is already running on any instance
3. **Assignment**: If not running, assign to least loaded instance
4. **Context Management**: Handle `num_ctx` parameter intelligently
5. **Proxying**: Route to determined instance

### Load Balancing Strategy

- **Least Connections**: Uses `least_conn` for general endpoints
- **Model Affinity**: Routes requests for same model to same instance
- **Health Monitoring**: 3 max fails, 15-minute timeout

### Background Processes

- **Model Mapping Updates**: Every 3 seconds
- **GPU Metrics Collection**: Every 2 seconds (worker 0 only)
- **Shared Memory**: Uses Lua shared dictionaries for state

## Configuration Variables

| Variable              | Source      | Purpose                        |
| --------------------- | ----------- | ------------------------------ |
| `$target_instance`    | Lua logic   | Determined target for proxying |
| `$endpoint`           | URL capture | API endpoint being accessed    |
| `$connection_upgrade` | Header map  | WebSocket support              |

## Error Handling

- **Timeouts**: 900 seconds for LLM operations
- **Retries**: 3 max fails per instance
- **Fallback**: 500 errors when no instance available
- **Health Checks**: Automatic instance health monitoring
