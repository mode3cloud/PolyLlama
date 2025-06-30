# PolyLlama Architecture Rules

This document defines the immutable architectural principles and communication patterns that MUST be followed when developing PolyLlama components.

## Core Architectural Laws

### Law 1: Server-Side Only Communication
**All inter-service communication MUST happen server-side.** Client browsers can NEVER directly access Docker service names or internal ports.

❌ **FORBIDDEN**: 
```javascript
// Client-side code
fetch('http://llm-proxy:11435/api/chat')  // NEVER DO THIS
fetch('http://ollama1:11434/api/generate') // NEVER DO THIS
```

✅ **REQUIRED**:
```javascript
// Client-side code
fetch('/ui/api/chat')  // Goes through Next.js server
fetch('/api/models')   // Goes through Nginx proxy
```

### Law 2: API Endpoint Routing Patterns

The system exposes TWO distinct API patterns with different purposes:

#### Pattern A: `/api/*` - Direct Ollama Access (via Nginx)
- **Purpose**: Dashboard monitoring, direct Ollama operations
- **Flow**: Browser → Nginx (:11434) → Lua Router → Ollama Instance
- **Authentication**: MUST include API-KEY header
- **Example**: `/api/models`, `/api/tags`, `/api/generate`

#### Pattern B: `/ui/api/*` - Next.js API Routes
- **Purpose**: Application features (chat, email, agents)
- **Flow**: Browser → Nginx → Next.js (:3000) → Internal Services
- **Authentication**: JWT/OAuth protected
- **Example**: `/ui/api/chat`, `/ui/api/agent/workflow`

### Law 3: Authentication Hierarchy

1. **External `/api/*` endpoints**: ALWAYS require API-KEY header
2. **External `/ui/api/*` endpoints**: Protected by JWT/OAuth
3. **Internal service calls**: When Next.js calls `/api/*` internally, it MUST include API-KEY
4. **Service-to-service**: Internal services communicate without public authentication

❌ **FORBIDDEN**:
```typescript
// Next.js server-side code calling Ollama
const response = await fetch('http://localhost:11434/api/chat', {
  body: JSON.stringify(payload)
  // Missing API-KEY header!
})
```

✅ **REQUIRED**:
```typescript
// Next.js server-side code
const response = await fetch('http://localhost:11434/api/chat', {
  headers: {
    'api-key': process.env.POLYLLAMA_API_KEY,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(payload)
})
```

### Law 4: Service Communication Map

```
┌─────────────────────────────────────────────────────────────┐
│ Service              │ Can Call                             │
├─────────────────────────────────────────────────────────────┤
│ Browser              │ /api/*, /ui/api/*                    │
│ Next.js              │ llm-proxy:11435, agent:11436,        │
│                      │ localhost:11434/api/*                │
│ Agent Controller     │ llm-proxy:11435, MCP services        │
│ LLM Proxy (litellm)  │ localhost:11434/api/*, external APIs │
│ Nginx                │ polyllama1-N:11434, nextjs:3000      │
└─────────────────────────────────────────────────────────────┘
```

### Law 5: LLM Proxy Integration

The LLM Proxy (litellm) is the ONLY service that should make LLM inference calls:

1. **All LLM requests go through the proxy** at `http://llm-proxy:11435`
2. **The proxy handles provider routing** (Ollama, OpenAI, Anthropic, etc.)
3. **Ollama requests are forwarded** to `localhost:11434` with API-KEY
4. **Never bypass the proxy** for LLM operations in new features

❌ **FORBIDDEN**:
```python
# Agent code directly calling Ollama
response = requests.post('http://localhost:11434/api/chat', ...)
```

✅ **REQUIRED**:
```python
# Agent code using LLM proxy
response = requests.post('http://llm-proxy:11435/v1/chat/completions', ...)
```

### Law 6: Streaming Response Rules

All components MUST support streaming for real-time user feedback:

1. **Never buffer entire responses** before sending to client
2. **Use appropriate streaming mechanisms**:
   - SSE (Server-Sent Events) for unidirectional streams
   - HTTP chunked encoding for simple streams
   - WebSockets only for bidirectional communication
3. **Transform streams properly**:
   ```typescript
   // NEVER lock the stream before transformation
   ❌ const reader = response.body.getReader() // Locks the stream!
   ✅ const transformed = response.body.pipeThrough(new TransformStream({...}))
   ```

### Law 7: Docker Service Naming

1. **Ollama instances**: `polyllama1`, `polyllama2`, etc. (NOT `ollama1`)
2. **Support services**: Use descriptive names (`llm-proxy`, `agent-controller`)
3. **Container names**: Match service names for clarity
4. **Network**: All services on `polyllama-network`

### Law 8: Configuration Propagation

Environment variables flow in this specific order:

```
.env file
    ↓
docker-compose.yml (env_file directive)
    ↓
Container environment
    ↓
Nginx shared memory (for Lua)
    ↓
Application runtime
```

Critical variables:
- `POLYLLAMA_API_KEY`: For API protection
- `OLLAMA_INSTANCE_COUNT`: For routing logic
- `POLYLLAMA_CPU_ROUTING_MODE`: For mixed deployments

### Law 9: Error Handling Patterns

1. **Network errors**: Always retry with exponential backoff
2. **Authentication errors**: Never retry, fail immediately
3. **Streaming errors**: Gracefully close streams with error message
4. **Service unavailable**: Return 503 with retry-after header

### Law 10: File System Access

1. **Generated files**: Only in `builder/built/` directory
2. **Static files**: Remain in their template locations
3. **Logs**: Use Docker logging drivers, not file logs
4. **Temporary files**: Use `/tmp` in containers, clean up immediately

## Communication Flow Examples

### Example 1: Chat Request Flow

```
1. Browser: POST /ui/api/chat
   Headers: { Authorization: "Bearer <JWT>" }
   
2. Nginx: Route to Next.js
   Strips /ui prefix → POST /api/chat
   
3. Next.js: Validate JWT, call LLM proxy
   POST http://llm-proxy:11435/v1/chat/completions
   
4. LLM Proxy: Route to Ollama
   POST http://localhost:11434/api/chat
   Headers: { api-key: "<KEY>" }
   
5. Nginx (port 11434): Route to instance
   Lua logic → polyllama2:11434
   
6. Response streams back through the same path
```

### Example 2: Agent Workflow

```
1. Browser: POST /ui/api/agent/workflow
   Headers: { Authorization: "Bearer <JWT>" }
   
2. Next.js: Stream to agent controller
   POST http://agent-controller:11436/workflow
   
3. Agent: Multiple LLM calls via proxy
   POST http://llm-proxy:11435/v1/chat/completions
   
4. Agent: Tool execution
   Direct calls to MCP services
   
5. Stream partial results back to browser
```

## Testing Requirements

Before deploying any new feature:

1. **Unit tests**: Service isolation with mocked dependencies
2. **Integration tests**: Full flow with all services running
3. **Security tests**: Attempt bypassing authentication
4. **Load tests**: Concurrent requests to verify routing
5. **Streaming tests**: Verify partial response delivery

## Monitoring Requirements

Every service MUST expose:

1. **Health endpoint**: `/health` returning 200 when ready
2. **Metrics endpoint**: `/metrics` in Prometheus format
3. **Structured logs**: JSON format with correlation IDs
4. **Trace propagation**: OpenTelemetry headers

## Security Checklist

- [ ] All external endpoints authenticated
- [ ] Service-to-service calls use internal networks
- [ ] Secrets in environment variables, not code
- [ ] Input validation on all user data
- [ ] Output sanitization before streaming
- [ ] Rate limiting on all endpoints
- [ ] Audit logging for sensitive operations

## Anti-Patterns to Avoid

1. **Synchronous blocking**: Always use async/await
2. **Hardcoded endpoints**: Use environment variables
3. **Direct Ollama access**: Always go through LLM proxy
4. **Client-side service calls**: Always proxy through Next.js
5. **Buffering streams**: Always stream progressively
6. **Skipping authentication**: Every external endpoint needs auth
7. **Ignoring errors**: Always handle and log errors properly

## Golden Rules Summary

1. **Client can only call `/api/*` and `/ui/api/*`**
2. **All LLM operations go through the LLM proxy**
3. **Authentication is non-negotiable on external endpoints**
4. **Streaming is required for all LLM responses**
5. **Server-side can call internal services directly**
6. **Never expose internal service names to clients**
7. **Always validate input and sanitize output**
8. **Follow the service communication map strictly**

These rules ensure security, scalability, and maintainability of the PolyLlama system.