# 🦙 PolyLlama

[![CI](https://github.com/mode3cloud/polyllama/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mode3cloud/polyllama/actions/workflows/ci.yml)
[![Coverage Report](https://img.shields.io/badge/coverage-report-brightgreen)](https://mode3cloud.github.io/PolyLlama/)

## Dynamic, Multi-Instance Ollama Orchestration for Local AI Power

PolyLlama is an open source stack for running [Ollama](https://ollama.com) in advanced local and homelab environments. It **automatically detects your hardware**, intelligently groups GPUs, dynamically generates Docker Compose configs, and provides powerful routing, load balancing, and monitoring for LLM workloads.

> PolyLlama makes it trivial to harness all your GPUs and CPUs for generative AI—no manual configuration required.

---

## 📷 Screenshots

### Launch `./polyllama.sh`

<img src="docs/images/startup.png" alt="PolyLLama Startup Output" width="800"/>

### UI Console `http://localhost:11434/`

<img src="docs/images/ui-console.png" alt="PolyLLama UI Console" width="1200"/>


### Load Model

<img src="docs/images/load-model.png" alt="PolyLLama Load Model" width="550"/>

---

## 🏗️ Dynamic Architecture

PolyLlama **discovers your system’s capabilities** and generates the optimal deployment—whether you have a single GPU, a mixed multi-GPU workstation, or a humble CPU-only server.

### 🎯 **Automatic GPU Detection & Grouping**

* **Detects all NVIDIA GPUs** via `nvidia-smi` (using consistent PCI bus ordering)
* **Groups identical GPU models** together for maximal efficiency
* **Creates dedicated Ollama instances** per group, auto-setting `CUDA_VISIBLE_DEVICES`
* **Generates** `generated-compose.yml` on-the-fly using a Jinja2 template

### 📊 **Example Configurations**

#### Multi-GPU Workstation

```mermaid
graph TD
  subgraph "Load Balancer"
    Router["🔀 Nginx Router<br/>:11434"]
  end

  subgraph "PolyLlama Instances"
    P1["🦙 polyllama1<br/>RTX 6000 Ada<br/>GPU 3"]
    P2["🦙 polyllama2<br/>RTX 4090<br/>GPUs 0,1,2"]
  end

  subgraph "Hardware Detection"
    GPU0["🎮 RTX 4090<br/>GPU 0"]
    GPU1["🎮 RTX 4090<br/>GPU 1"] 
    GPU2["🎮 RTX 4090<br/>GPU 2"]
    GPU3["🖥️ RTX 6000 Ada<br/>GPU 3"]
  end

  Router --> P1
  Router --> P2

  P1 --> GPU3
  P2 --> GPU0
  P2 --> GPU1
  P2 --> GPU2

  style P1 fill:#e1f5fe
  style P2 fill:#f3e5f5
  style Router fill:#fff3e0
```

#### Gaming Laptop

```mermaid
graph TD
  subgraph "Load Balancer"
    Router["🔀 Nginx Router<br/>:11434"]
  end

  subgraph "PolyLlama Instance"
    P1["🦙 polyllama1<br/>RTX 4070<br/>GPU 0"]
  end

  subgraph "Hardware Detection"
    GPU0["🎮 RTX 4070<br/>GPU 0"]
  end

  Router --> P1
  P1 --> GPU0

  style P1 fill:#e8f5e8
  style Router fill:#fff3e0
```

#### CPU-Only System

```mermaid
graph TB
  Router["🔀 Nginx Router<br/>:11434"]
  P1["🦙 polyllama1<br/>CPU Mode<br/>16GB Memory"]
  CPU["💻 CPU Only<br/>No GPUs Detected"]

  Router --> P1
  P1 --> CPU

  style P1 fill:#fce4ec
  style Router fill:#fff3e0
```

---

## 🔀 API Request Flow Architecture

### Direct Ollama API Calls

When you make requests to `localhost:11434/api/*`, PolyLlama intelligently routes them:

#### PolyLlama Internal Endpoints

These endpoints provide PolyLlama-specific functionality and are protected by the same API key authentication as standard Ollama endpoints when `POLYLLAMA_API_KEY` is configured.

| Endpoint | Method | Description | Implementation |
|----------|--------|-------------|----------------|
| `/api/polyllama/instance-status` | GET | Returns health status of all PolyLlama instances | Polls each instance's `/api/version` endpoint |
| `/api/polyllama/instance-count` | GET | Returns the number of configured instances | Reads from shared memory `OLLAMA_INSTANCE_COUNT` |
| `/api/polyllama/gpu-config` | GET | Returns GPU configuration and instance mapping | Static config from build-time template |
| `/api/polyllama/gpu-metrics` | GET | Returns real-time GPU/CPU metrics for all instances | Collects from instance metrics endpoints every 2s |
| `/api/polyllama/running-models` | GET | Returns all currently loaded models across instances | Aggregates from all instance `/api/ps` endpoints |
| `/api/polyllama/model-details` | POST | Get detailed info for a specific model | Routes to appropriate instance's `/api/show` |
| `/api/polyllama/model-mappings` | GET | Returns model-to-instance mappings and cache | Shows internal routing state |
| `/api/polyllama/get-contexts` | GET | Returns stored context lengths for models | Reads from shared memory context cache |
| `/api/polyllama/store-context` | POST | Stores context length for a model | Writes to shared memory for num_ctx tracking |
| `/api/polyllama/clean-mappings` | POST | Removes mappings for unloaded models | Cleans up stale routing entries |
| `/api/polyllama/duplicate-models` | GET | Detects models loaded on multiple instances | Helps identify routing issues |
| `/api/polyllama/sync-contexts` | POST | Syncs context sizes from running models | Updates context cache from loaded models |
| `/api/polyllama/search-models` | GET | Search models on ollama.com | Proxies to ollama.com model search |
| `/api/polyllama/pull-model` | POST | Initiate model pull to specific instance | Starts async model download |
| `/api/polyllama/pull-status` | GET | Get status of a model pull operation | Tracks download progress |
| `/api/polyllama/pull-statuses` | GET | Get all active pull operations | Lists all ongoing downloads |
| `/api/*` | ALL | Standard Ollama API endpoints | Load-balanced routing with model affinity |

```mermaid
graph TB
    subgraph "Clients"
        Browser["🌐 Web UI<br/>localhost:11434/ui"]
        API["🔧 API Client<br/>(curl, SDK, etc.)"]
    end
    
    subgraph "PolyLlama Router [:11434]"
        subgraph "API Endpoints"
            Internal["📊 /api/polyllama/*<br/>Internal Management APIs"]
            Ollama["🦙 /api/*<br/>Standard Ollama APIs"]
        end
        
        subgraph "Routing Logic"
            Lua["📜 Lua Router<br/>(model_router.lua)"]
            Memory["💾 Shared Memory<br/>• Model mappings<br/>• Context sizes<br/>• Instance count<br/>• GPU metrics"]
        end
    end
    
    subgraph "Backend Services"
        P1["🦙 polyllama1<br/>RTX 4090 x3<br/>:11434"]
        P2["🦙 polyllama2<br/>RTX 6000 Ada<br/>:11434"]
        P3["🦙 polyllama3<br/>CPU Only<br/>:11434"]
        
        GPU1["🎮 GPU Metrics<br/>:11435"]
        GPU2["🎮 GPU Metrics<br/>:11435"]
    end
    
    subgraph "External Services"
        OllamaHub["🌍 ollama.com<br/>Model Search"]
    end
    
    %% Client connections
    Browser -->|"Monitor & Control"| Internal
    API -->|"LLM Operations"| Ollama
    
    %% Internal API flows
    Internal -->|"Read/Write"| Memory
    Internal -->|"Status Checks"| P1
    Internal -->|"Status Checks"| P2
    Internal -->|"Status Checks"| P3
    Internal -->|"Model Search"| OllamaHub
    
    %% Ollama API flows
    Ollama -->|"Route Request"| Lua
    Lua -->|"Check Mappings"| Memory
    Lua -->|"Model Affinity<br/>or Load Balance"| P1
    Lua -->|"Model Affinity<br/>or Load Balance"| P2
    Lua -->|"Model Affinity<br/>or Load Balance"| P3
    
    %% Metrics collection
    GPU1 -.->|"Collect GPU Data"| Memory
    GPU2 -.->|"Collect GPU Data"| Memory
    P3 -.->|"Collect CPU Data"| Memory
    
    %% Instance associations
    P1 -.->|"Metrics"| GPU1
    P2 -.->|"Metrics"| GPU2
    
    style Browser fill:#e3f2fd
    style API fill:#e1f5fe
    style Internal fill:#f3e5f5
    style Ollama fill:#fff3e0
    style Lua fill:#fce4ec
    style Memory fill:#e8f5e9
    style P1 fill:#c8e6c9
    style P2 fill:#ffccbc
    style P3 fill:#f5f5f5
    style OllamaHub fill:#b3e5fc
```

#### How PolyLlama Routes Requests

1. **Internal Management APIs** (`/api/polyllama/*`)
   * Used by the Web UI for monitoring and control
   * Direct access to shared memory for instant status
   * Aggregate data from all instances (models, metrics, status)
   * Manage model downloads and routing configuration

2. **Standard Ollama APIs** (`/api/*`)
   * Compatible with all Ollama clients and SDKs
   * Smart routing based on model affinity
   * Automatic load balancing for new models
   * Context size preservation across requests

3. **Shared Memory Store**
   * Model-to-instance mappings for sticky routing
   * Context sizes to maintain model performance
   * GPU/CPU metrics updated every 2 seconds
   * Instance configuration from startup

### Web UI Chat Interface Flow
The chat interface uses a multi-tier architecture for provider flexibility:

```mermaid
graph LR
    subgraph "Browser"
        UI["🌐 Chat UI<br/>/ui/chat"]
    end
    
    subgraph "Next.js Server"
        API["📡 API Routes<br/>/ui/api/chat/*"]
    end
    
    subgraph "LLM Proxy"
        Proxy["🔄 litellm<br/>:11435"]
    end
    
    subgraph "Providers"
        Ollama["🦙 Ollama<br/>via :11434/api"]
        OpenAI["🤖 OpenAI API"]
        Anthropic["🧠 Anthropic API"]
    end
    
    UI -->|"fetch('/ui/api/chat/completions')"| API
    API -->|"Server-side proxy to llm-proxy:11435"| Proxy
    Proxy -->|"Route based on model"| Ollama
    Proxy -->|"gpt-4"| OpenAI
    Proxy -->|"claude-3"| Anthropic
    
    Ollama -->|"Via Nginx router"| P1["🦙 polyllama1"]
    
    style UI fill:#e3f2fd
    style API fill:#f3e5f5
    style Proxy fill:#fff3e0
    style Ollama fill:#e8f5e9
    style OpenAI fill:#e1f5fe
    style Anthropic fill:#fce4ec
```

**Key Architecture Points:**
- **Server-side only**: Browser never directly calls Docker services
- **Unified endpoint**: Everything accessible via `localhost:11434`
- **Smart routing**: Models automatically distributed across instances
- **Multi-provider**: Chat UI supports Ollama, OpenAI, Anthropic, etc.

---

## 🚀 Quick Start

### 1. **Clone the Repo**

```bash
git clone https://github.com/your-org/polyllama.git
cd polyllama
```

### 2. **Run the Launch Script**

```bash
# Auto-detect hardware and launch
./polyllama.sh

# See detected configuration
./polyllama.sh --detect

# Stop all services
./polyllama.sh --stop

# View logs
./polyllama.sh --logs

# Check status
./polyllama.sh --status
```

* **Dynamic Detection:**

  * *Multiple GPU types:* Each group gets its own instance
  * *Single GPU type:* All GPUs pooled for one instance
  * *No GPUs:* CPU-only Ollama
  * *Generates* `generated-compose.yml` dynamically

---

## 🌐 Access Points

* **Model Management Web UI**: [http://localhost:11434/ui/](http://localhost:11434/ui/)
* **Open Web UI (for local testing)**: [http://localhost:5000/](http://localhost:5000/)
* **API Endpoint**: [http://localhost:11434/api/](http://localhost:11434/api/)
* **Olah Mirror (for more efficient multi container HF downloads)**: [http://localhost:8090/](http://localhost:8090/)

---

## ✨ Features

* **Auto Hardware Discovery** (NVIDIA/CPU)
* **Dynamic Instance Grouping** (per GPU model)
* **Intelligent Model Routing & Load Balancing**
* **Context-Aware Model Loading**
* **Customizable via .env**
* **Modern Web UI for Monitoring & Management**
* **Nginx Proxy for Scalable Access**
* **Scripted Health Checks and Real-Time Status**

---

## 🖥️ Web Interface

* See all PolyLlama/Ollama instances, GPUs, and loaded models
* One-click model load/unload
* Set custom context lengths and manage assignments
* Visualize routing and system status live

---

## 🔧 Configuration

**Copy the `.env.example` to `.env` and set:**

```bash
POLYLLAMA_API_KEY=<your_api_key>  # Optional: API key to protect /api endpoints
HF_TOKEN=<your_hf_token>          # HuggingFace token for model access
```

### API Key Protection (Optional)
If `POLYLLAMA_API_KEY` is set, ALL `/api/*` endpoints (including both Ollama and PolyLlama management endpoints) will require authentication via one of:
- `api-key: <your_api_key>` header
- `x-api-key: <your_api_key>` header  
- `Authorization: Bearer <your_api_key>` header

---

## 🔒 Security Architecture

PolyLlama implements a comprehensive security model with multiple layers of authentication to protect LLM access:

### Authentication Overview

```mermaid
graph TD
    subgraph "External Access"
        Browser["🌐 Browser/Client"]
        API["🔧 API Client"]
    end
    
    subgraph "PolyLlama Security Layers"
        NextJS["🔐 Next.js App<br/>(OAuth Protected)"]
        Nginx["🛡️ Nginx Router<br/>(API Key Protected)"]
        LLMProxy["🤖 LLM Proxy<br/>(Internal Only)"]
    end
    
    subgraph "LLM Backends"
        Ollama["🦙 Ollama Instances"]
        OpenAI["🤖 OpenAI API"]
        Anthropic["🧠 Anthropic API"]
    end
    
    Browser -->|"/ui/*<br/>OAuth Required"| NextJS
    API -->|"/api/*<br/>API Key Required"| Nginx
    
    NextJS -->|"Internal<br/>llm-proxy:11435"| LLMProxy
    Nginx -->|"Internal<br/>Load Balanced"| Ollama
    
    LLMProxy -->|"With API Key"| Nginx
    LLMProxy -->|"With Provider Keys"| OpenAI
    LLMProxy -->|"With Provider Keys"| Anthropic
    
    style NextJS fill:#e3f2fd
    style Nginx fill:#fff3e0
    style LLMProxy fill:#f3e5f5
```

### Security Layers

#### 1. **Web UI Access (`/ui/*` routes)**
- **Protection**: Azure OAuth / OIDC authentication
- **Scope**: All UI pages and `/ui/api/*` endpoints
- **Implementation**: Next.js middleware validates OAuth tokens
- **Use Case**: Interactive web access for authenticated users

#### 2. **API Access (`/api/*` routes)**
- **Protection**: POLYLLAMA_API_KEY authentication
- **Scope**: ALL `/api/*` endpoints including:
  - Standard Ollama API endpoints (e.g., `/api/generate`, `/api/chat`)
  - PolyLlama management endpoints (e.g., `/api/polyllama/instance-status`)
- **Implementation**: Nginx Lua scripts validate API keys
- **Supported Headers**:
  - `api-key: <your_api_key>`
  - `x-api-key: <your_api_key>`
  - `Authorization: Bearer <your_api_key>`
- **Use Case**: Direct API access for external applications and management tools

#### 3. **LLM Proxy (Internal Only)**
- **Protection**: No external access (no exposed ports)
- **Access**: Only via internal Docker network (`http://llm-proxy:11435`)
- **Purpose**: Unified interface for multiple LLM providers
- **Authentication**: Automatically includes POLYLLAMA_API_KEY when calling Ollama

### Request Flow Examples

#### Example 1: Web UI Chat Request
```
Browser → /ui/api/chat/completions (OAuth required)
  → Next.js validates OAuth token
  → Next.js server → http://llm-proxy:11435/api/chat/completions
  → LLM Proxy routes to appropriate provider:
    - If Ollama model: → http://router:11434/api/chat (with POLYLLAMA_API_KEY)
    - If OpenAI model: → OpenAI API (with OPENAI_API_KEY)
    - If Anthropic model: → Anthropic API (with ANTHROPIC_API_KEY)
```

#### Example 2: Direct API Request
```
External Client → /api/generate (POLYLLAMA_API_KEY required)
  → Nginx validates API key
  → Nginx load balances to Ollama instance
  → Response returned to client
```

### Security Benefits

1. **No Direct LLM Access**: External clients cannot directly access the LLM proxy or individual Ollama instances
2. **Dual Authentication**: Different authentication methods for different use cases (OAuth for UI, API key for programmatic access)
3. **Internal Service Isolation**: LLM proxy is completely isolated from external access
4. **Credential Protection**: Provider API keys (OpenAI, Anthropic) are never exposed to clients
5. **Audit Trail**: All requests are authenticated and can be logged for security auditing

### Configuration

To enable full security:

1. **Set OAuth Provider** (for UI access):
   ```bash
   # In .env file
   OAUTH_CLIENT_ID=your-oauth-client-id
   OAUTH_CLIENT_SECRET=your-oauth-client-secret
   OAUTH_ISSUER=https://your-oauth-provider.com
   ```

2. **Set API Key** (for API access):
   ```bash
   # In .env file
   POLYLLAMA_API_KEY=your-secure-api-key
   ```

3. **Set LLM Provider Keys** (as needed):
   ```bash
   # In .env file
   OPENAI_API_KEY=your-openai-key
   ANTHROPIC_API_KEY=your-anthropic-key
   ```

---

## 📊 Monitoring & Management

* **Health:** Real-time status for all PolyLlama instances
* **Resource Usage:** GPU/CPU memory, model assignments
* **Load Balancing:** Least-connections with failover
* **Logs & Debugging:** Scripted helpers and Compose logs

---

## 🛠️ Advanced Usage

* **Custom Model Loading:**
  Use the UI to load/unload models, set context, and assign to instances
* **Direct API:**
  Target automatic routing or force a specific instance via API

---

## 🐛 Troubleshooting

```bash
./polyllama.sh --status
./polyllama.sh --logs
docker-compose logs polyllama1    # View logs for a specific instance
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
docker exec polyllama1 nvidia-smi # Check GPU access in running instance
```

**Reset Everything:**

```bash
./polyllama.sh --stop
docker system prune -f
./polyllama.sh
```

---

## 🤝 Contributing

PolyLlama is **open source** and welcomes community involvement!

* **Code contributions** (detection logic, new features, UI)
* **Docs & How-tos**
* **Bug reports & feature requests**
* **Testing on unique hardware**
* **LLM-based UX helpers**

Want to get involved? [Open an issue](https://github.com/mode3cloud/polyllama/issues) or [start a discussion](https://github.com/mode3cloud/polyllama/discussions)!

---

## 🛣️ Roadmap & Potential Future Ideas

Some cool directions PolyLlama could go next:

* **LLM-powered Config Wizard:**
  Use an LLM to interpret your hardware, usage goals, and preferences to generate an ideal configuration (including model placement, memory tuning, and advanced routing).
* **AMD & Apple GPU Support:**
  Expand beyond NVIDIA via ROCm/Metal backends as supported by Ollama and the community.
* **Unified Model Marketplace:**
  Integrated access to community models, HuggingFace, and private model hubs.
* **More Granular Model Pinning:**
  Assign specific models or jobs to preferred GPU classes or nodes.
* **User Profiles & Access Control:**
  Fine-tune who can manage or use PolyLlama.
* **Cluster/Networked Mode:**
  Deploy PolyLlama across several physical nodes (for true AI at scale).
* **Metrics & Alerting Integrations:**
  Prometheus/Grafana or Discord/Slack bots for real-time health alerts.
* **Self-Updating Stack:**
  Automated update flow for the full system (including dependencies).

Have ideas or want to help build the next phase? **Contributions are encouraged!**

---

## License

[MIT License](LICENSE)

---

## Credits

PolyLlama is built on the excellent [Ollama](https://ollama.com) open source project, and includes [Open WebUI](https://github.com/open-webui/open-webui) for ease of testing and [Olah](https://github.com/vtuber-plan/olah) to reduce multiple model downloads.

🦙🦙🦙 Thanks to all AI and open hardware enthusiasts whose work makes local AI possible! 🦙🦙🦙

---

*Let the llamas run wild on your silicon.*
— The PolyLlama Team

---
