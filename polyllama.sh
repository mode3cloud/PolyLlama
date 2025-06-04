#!/bin/bash

# Ollama Stack Launcher
# Automatically detects hardware and selects appropriate configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to display usage
usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Ollama stack launcher with automatic hardware detection:"
    echo ""
    echo "  [no args]       Auto-detect hardware and launch appropriate config"
    echo "  --stop          Stop all services"
    echo "  --logs          Show logs from all services"
    echo "  --status        Show status of all services"
    echo "  --detect        Show detected hardware configuration"
    echo "  --debug         Enable debug mode (show build output on console)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Hardware Detection:"
    echo "  - Multiple GPU types → One instance per GPU type group"
    echo "  - Single GPU type    → One instance with all GPUs"
    echo "  - 0 GPUs            → CPU-only configuration"
    echo ""
    echo "Examples:"
    echo "  $0              # Auto-detect and launch"
    echo "  $0 --detect     # Show what would be detected"
    echo "  $0 --debug      # Launch with debug output on console"
    echo "  $0 --stop       # Stop all services"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        echo "Error: Docker is not running or not accessible"
        echo "Please start Docker and try again"
        exit 1
    fi
}

# Function to detect and group GPUs by type
detect_gpu_groups() {
    local gpu_info_file=$(mktemp)
    local gpu_groups=()
    
    # Try to get GPU information
    if command -v nvidia-smi >/dev/null 2>&1; then
        # Get GPU names and indices with consistent ordering
        CUDA_DEVICE_ORDER=PCI_BUS_ID nvidia-smi --query-gpu=index,name,pci.bus_id --format=csv,noheader,nounits > "$gpu_info_file" 2>/dev/null || true
        echo "🔍 Detected GPUs using nvidia-smi (PCI bus order):"
    elif docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi --query-gpu=index,name,pci.bus_id --format=csv,noheader,nounits > "$gpu_info_file" 2>/dev/null; then
        echo "🔍 Detected GPUs using Docker NVIDIA runtime:"
    else
        echo "⚠️  No GPUs detected or NVIDIA runtime unavailable"
        rm -f "$gpu_info_file"
        return
    fi
    
    # Parse GPU information and group by type
    declare -A gpu_type_groups
    declare -A gpu_type_names
    
    while IFS=',' read -r index name pci_bus; do
        # Clean up the strings
        index=$(echo "$index" | xargs)
        name=$(echo "$name" | xargs)
        pci_bus=$(echo "$pci_bus" | xargs)
        
        if [ -n "$name" ]; then
            echo "  GPU $index: $name ($pci_bus)"
            
            # Group GPUs by name (type)
            if [ -z "${gpu_type_groups[$name]}" ]; then
                gpu_type_groups[$name]="$index"
                gpu_type_names[$name]="$name"
            else
                gpu_type_groups[$name]="${gpu_type_groups[$name]},$index"
            fi
        fi
    done < "$gpu_info_file"
    
    rm -f "$gpu_info_file"
    
    # Convert to global arrays for later use
    GPU_GROUPS=()
    GPU_GROUP_NAMES=()
    GPU_GROUP_INDICES=()
    
    for gpu_type in "${!gpu_type_groups[@]}"; do
        GPU_GROUPS+=("$gpu_type")
        GPU_GROUP_NAMES+=("$gpu_type")
        GPU_GROUP_INDICES+=("${gpu_type_groups[$gpu_type]}")
    done
    
    echo ""
    echo "📊 GPU Grouping Results:"
    if [ ${#GPU_GROUPS[@]} -eq 0 ]; then
        echo "  No GPU groups found - will use CPU-only configuration"
        DETECTED_GPU_COUNT=0
        DETECTED_CONFIG="cpu-only"
    else
        for i in "${!GPU_GROUPS[@]}"; do
            local indices="${GPU_GROUP_INDICES[$i]}"
            local count=$(echo "$indices" | tr ',' '\n' | wc -l)
            echo "  Group $((i+1)): ${GPU_GROUP_NAMES[$i]} (GPUs: $indices) - $count GPU(s)"
        done
        
        DETECTED_GPU_COUNT=$(echo "${GPU_GROUP_INDICES[@]}" | tr ',' '\n' | tr ' ' '\n' | grep -v '^$' | wc -l)
        DETECTED_CONFIG="dynamic-${#GPU_GROUPS[@]}-groups"
    fi
}

# Function to generate docker-compose file from template
generate_compose_file() {
    
    echo "🔨 Generating automatic compose definition from template..."
    
    # Prepare GPU configuration JSON for the Python script
    local gpu_config_json='{"gpu_groups":['
    
    if [ ${#GPU_GROUPS[@]} -eq 0 ]; then
        # CPU-only configuration
        gpu_config_json='{"gpu_groups":[]}'
        echo "  Generating CPU-only configuration"
    else
        # GPU-based configurations
        local group_configs=()
        for i in "${!GPU_GROUPS[@]}"; do
            local gpu_indices="${GPU_GROUP_INDICES[$i]}"
            local gpu_name="${GPU_GROUP_NAMES[$i]}"
            
            # Convert comma-separated indices to JSON array
            local indices_array="[$(echo "$gpu_indices" | sed 's/,/,/g')]"
            
            local group_config="{\"name\":\"$gpu_name\",\"indices\":$indices_array}"
            group_configs+=("$group_config")
            
            echo "  Configuring instance $((i+1)) for $gpu_name (GPUs: $gpu_indices)"
        done
        
        # Join group configs with commas
        local joined_groups=$(IFS=,; echo "${group_configs[*]}")
        gpu_config_json="{\"gpu_groups\":[$joined_groups]}"
    fi
    
    # Generate compose file using Python template renderer
    if ! python3 builder/generate_compose.py "$gpu_config_json"; then
        echo "❌ Failed to generate automatic docker compose definition from template"
        exit 1
    fi
    
    # Set global variables
    local instance_count=${#GPU_GROUPS[@]}
    if [ $instance_count -eq 0 ]; then
        instance_count=1
    fi
    
    DETECTED_COMPOSE_FILE="runtime/docker-compose.yml"
    DETECTED_INSTANCE_COUNT=$instance_count
}

# Function to show detected hardware configuration
show_detection() {
    echo "🔍 Starting hardware detection..."
    echo ""
    
    detect_gpu_groups
    generate_compose_file
    
    echo ""
    echo "📋 Final Configuration Summary:"
    echo "  Total GPUs: $DETECTED_GPU_COUNT"
    echo "  GPU Groups: ${#GPU_GROUPS[@]}"
    echo "  Ollama Instances: $DETECTED_INSTANCE_COUNT"
    echo "  Configuration: $DETECTED_CONFIG"
    echo "  Generated file: $DETECTED_COMPOSE_FILE"
    echo ""
    
    if [ ${#GPU_GROUPS[@]} -eq 0 ]; then
        echo "  🖥️  CPU-Only Configuration:"
        echo "    - No GPUs detected or NVIDIA runtime unavailable"
        echo "    - Will create 1 Ollama instance using CPU only"
        echo "    - Suitable for smaller models and inference"
    else
        echo "  🎯 Dynamic GPU Configuration:"
        for i in "${!GPU_GROUPS[@]}"; do
            local instance_num=$((i+1))
            local gpu_indices="${GPU_GROUP_INDICES[$i]}"
            local gpu_count=$(echo "$gpu_indices" | tr ',' '\n' | wc -l)
            echo "    - Instance $instance_num: ${GPU_GROUP_NAMES[$i]} (GPUs: $gpu_indices) - $gpu_count GPU(s)"
        done
        echo "    - Each group gets dedicated Ollama instance"
        echo "    - OLLAMA_SCHED_SPREAD=1 for optimal GPU utilization"
        echo "    - CUDA_DEVICE_ORDER=PCI_BUS_ID for consistent ordering"
    fi
    
    echo ""
    echo "📄 Generated Docker Compose Preview:"
    echo "─────────────────────────────────────"
    head -50 "$DETECTED_COMPOSE_FILE" | sed 's/^/  /'
    echo "  ..."
    echo "─────────────────────────────────────"
}

# Function to launch stack with auto-detected configuration
launch_stack() {
    # Display cool ASCII banner
    echo ""
    echo "$(tput setaf 6)╔══════════════════════════════════════════════════════════════════════════════╗$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)                                                                              $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)   $(tput setaf 4)██████╗  ██████╗ ██╗  ██╗   ██╗██╗     ██╗      █████╗ ███╗   ███╗ █████╗$(tput sgr0)    $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)   $(tput setaf 4)██╔══██╗██╔═══██╗██║  ╚██╗ ██╔╝██║     ██║     ██╔══██╗████╗ ████║██╔══██╗$(tput sgr0)   $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)   $(tput setaf 4)██████╔╝██║   ██║██║   ╚████╔╝ ██║     ██║     ███████║██╔████╔██║███████║$(tput sgr0)   $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)   $(tput setaf 4)██╔═══╝ ██║   ██║██║    ╚██╔╝  ██║     ██║     ██╔══██║██║╚██╔╝██║██╔══██║$(tput sgr0)   $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)   $(tput setaf 4)██║     ╚██████╔╝███████╗██║   ███████╗███████╗██║  ██║██║ ╚═╝ ██║██║  ██║$(tput sgr0)   $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)   $(tput setaf 4)╚═╝      ╚═════╝ ╚══════╝╚═╝   ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝$(tput sgr0)   $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)                                                                              $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)   $(tput setaf 2)🦙 Dynamic Multi-Instance Ollama Orchestration for Local AI Power$(tput sgr0)           $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)                                                                              $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)   $(tput setaf 3)✨ Features:$(tput sgr0)                                                                $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)     $(tput setaf 7)• Auto GPU Detection & Grouping  • Intelligent Load Balancing$(tput sgr0)           $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)     $(tput setaf 7)• Dynamic Docker Compose Generation  • Modern Web Interface$(tput sgr0)             $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)                                                                              $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)   $(tput setaf 5)📖 Documentation & Source: https://github.com/mode3cloud/PolyLlama$(tput sgr0)      $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)║$(tput sgr0)                                                                              $(tput setaf 6)║$(tput sgr0)"
    echo "$(tput setaf 6)╚══════════════════════════════════════════════════════════════════════════════╝$(tput sgr0)"
    echo ""
    echo "🚀 Starting dynamic Ollama stack deployment..."
    echo ""
    
    # Detect hardware and generate compose file
    detect_gpu_groups
    generate_compose_file
    
    local compose_file="$DETECTED_COMPOSE_FILE"
    local config_name="$DETECTED_CONFIG"
    
    echo ""
    echo "🎯 Deployment Summary:"
    echo "  GPUs detected: $DETECTED_GPU_COUNT"
    echo "  GPU groups: ${#GPU_GROUPS[@]}"
    echo "  Ollama instances: $DETECTED_INSTANCE_COUNT"
    echo "  Generated file: $compose_file"
    
    # Stop any existing services
    echo "🛑 Stopping any existing services..."
    docker-compose -f "$compose_file" down --remove-orphans 2>/dev/null || true
    
    # Create log file with timestamp in runtime directory
    local log_file="runtime/polyllama-compose-build.log"
    
    # Pull latest images
    echo "📦 Pulling latest images..."
    if [ "$DEBUG_MODE" = "true" ]; then
        echo "   Debug mode: showing output on console"
        docker-compose -f "$compose_file" pull
    else
        echo "   Output logged to: $log_file"
        docker-compose -f "$compose_file" pull > "$log_file" 2>&1
    fi
    
    # Build services
    echo "🔨 Building services..."
    if [ "$DEBUG_MODE" = "true" ]; then
        echo "   Debug mode: showing output on console"
        docker-compose -f "$compose_file" build
    else
        echo "   This may take a few minutes... output logged to: $log_file"
        docker-compose -f "$compose_file" build >> "$log_file" 2>&1
    fi
    
    # Check if build was successful
    if [ $? -eq 0 ]; then
        echo "   ✅ Build completed successfully"
    else
        echo "   ❌ Build failed - check $log_file for details"
        echo ""
        echo "📋 Last 10 lines of build log:"
        tail -10 "$log_file"
        exit 1
    fi
    
    # Start services
    echo "▶️  Starting services..."
    docker-compose -f "$compose_file" up -d
    
    # Show status
    echo ""
    echo "✅ Dynamic Ollama stack launched successfully!"
    echo "🎯 Configuration: $DETECTED_INSTANCE_COUNT instance(s) across ${#GPU_GROUPS[@]} GPU group(s)"
    echo "🔍 Total GPUs: $DETECTED_GPU_COUNT"
    echo ""
    
    if [ ${#GPU_GROUPS[@]} -gt 0 ]; then
        echo "📊 Instance → GPU Mapping:"
        for i in "${!GPU_GROUPS[@]}"; do
            local instance_num=$((i+1))
            local gpu_indices="${GPU_GROUP_INDICES[$i]}"
            echo "  ollama$instance_num → ${GPU_GROUP_NAMES[$i]} (GPUs: $gpu_indices)"
        done
        echo ""
    fi
    
    echo "🌐 Web UI: http://localhost:11434/ui/"
    echo "🔧 API: http://localhost:11434/api/"
    echo "📊 Olah Mirror: http://localhost:8090/"
    echo ""
    echo "📋 Service Status:"
    docker-compose -f "$compose_file" ps
    echo ""
    echo "💡 Commands:"
    echo "  📜 View logs: ./polyllama.sh --logs"
    echo "  🛑 Stop: ./polyllama.sh --stop"
    echo "  📊 Status: ./polyllama.sh --status"
    echo "  🔍 Detect: ./polyllama.sh --detect"
    echo ""
    echo "📄 Generated compose file: $compose_file"
    echo "📋 Compose Build log: $log_file"
    echo ""
    echo "Thank you for using PolyLlama! 🦙"
}

# Function to stop services
stop_services() {
    echo "🛑 Stopping Polyllama stack..."
    
    local compose_file="runtime/docker-compose.yml"
    if [ -f "$compose_file" ]; then
        echo "  Stopping services from $compose_file..."
        docker-compose -f "$compose_file" down --remove-orphans 2>/dev/null || true
    fi
    
    echo "✅ All services stopped"
}

# Function to show logs
show_logs() {
    echo "📜 Showing logs from all services..."
    
    local compose_file="runtime/docker-compose.yml"
    if [ -f "$compose_file" ]; then
        if docker-compose -f "$compose_file" ps --services 2>/dev/null | grep -q .; then
            echo "  Logs from $compose_file:"
            docker-compose -f "$compose_file" logs --tail=50 -f
            return
        fi
    fi

    echo "❌ No running services found"
}

# Function to show status
show_status() {
    echo "📊 Service Status:"
    
    local compose_file="runtime/docker-compose.yml"
    if [ -f "$compose_file" ]; then
        echo ""
        echo "  From $compose_file:"
        if docker-compose -f "$compose_file" ps 2>/dev/null | grep -q "Up"; then
            docker-compose -f "$compose_file" ps
        else
            echo "    No services running"
        fi
    fi
}

# Function to check and create .env file
check_env_file() {
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            echo "📄 .env file not found, copying from .env.example..."
            cp ".env.example" ".env"
            echo "✅ Created .env file from .env.example"
            echo "💡 You may want to edit .env to customize your configuration"
        else
            echo "⚠️  .env file not found and .env.example doesn't exist"
            echo "   The stack will use default environment settings"
        fi
    fi
}

# Main logic
check_docker
check_env_file

# Set debug mode if requested
DEBUG_MODE=false
if [ "$1" = "--debug" ]; then
    DEBUG_MODE=true
fi

case "${1:-}" in
    "")
        # Default: auto-detect and launch
        launch_stack
        ;;
    --debug)
        # Debug mode: auto-detect and launch with debug output
        launch_stack
        ;;
    --detect)
        show_detection
        ;;
    --stop)
        stop_services
        ;;
    --logs)
        show_logs
        ;;
    --status)
        show_status
        ;;
    -h|--help)
        usage
        ;;
    *)
        echo "❌ Unknown option: $1"
        echo ""
        usage
        exit 1
        ;;
esac