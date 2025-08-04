# PolyLlama Project Brief

## Project Purpose
PolyLlama is a dynamic multi-instance Ollama orchestration system that automatically detects hardware and generates optimal deployments for local AI workloads. It transforms complex multi-GPU systems into intelligent, load-balanced AI infrastructure.

## Core Problem Solved
- **Manual Configuration Complexity**: Eliminates the need for manual Docker Compose and GPU assignment configuration
- **Resource Underutilization**: Automatically detects and optimally groups GPUs for maximum efficiency
- **Load Balancing**: Intelligently routes models to appropriate instances based on availability and load
- **Mixed Hardware Support**: Seamlessly handles different GPU types and CPU-only configurations

## Key Objectives
1. **Zero-Configuration Deployment**: Hardware detection drives automatic configuration generation
2. **Intelligent Load Distribution**: Smart routing ensures optimal resource utilization
3. **Unified API Interface**: Single endpoint (`:11434`) for all Ollama operations
4. **Developer Experience**: Rich web UI with monitoring, model management, and chat interfaces
5. **Extensibility**: Multi-provider LLM support via LiteLLM proxy
6. **Tool Integration**: MCP (Model Context Protocol) support for advanced AI capabilities

## Target Users
- **AI Researchers**: Running multiple models on complex GPU setups
- **Developers**: Building AI applications requiring reliable model orchestration
- **Homelab Enthusiasts**: Maximizing GPU utilization in personal servers
- **Teams**: Sharing GPU resources across multiple users and workloads

## Success Criteria
- Single command deployment (`./polyllama.sh`)
- Automatic hardware detection and optimal configuration generation
- Seamless model routing and load balancing
- Rich monitoring and management capabilities
- Support for mixed GPU/CPU deployments
- Extensible architecture for future enhancements

## Technical Constraints
- **Hardware**: NVIDIA GPU support via CUDA, CPU fallback capability
- **Platform**: Docker-based deployment on Linux systems
- **Dependencies**: Python 3.10+, Docker, nvidia-smi for GPU detection
- **Network**: Single-port exposure (11434) for all services
- **Security**: API key protection, JWT authentication for UI features

## Current Status
**Production Ready** - Core orchestration, routing, and UI features complete. Recent focus on MCP integration and tool streaming capabilities. System successfully handles dynamic GPU detection, intelligent routing, and comprehensive monitoring.