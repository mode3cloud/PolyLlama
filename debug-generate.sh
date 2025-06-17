#!/bin/bash
# Debug script to generate configs from JSON file without launching

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default to test artifact if no file specified
JSON_FILE="${1:-tests/test_artifacts/gpu_config.json}"

if [ ! -f "$JSON_FILE" ]; then
    echo "Error: JSON file not found: $JSON_FILE"
    echo "Usage: $0 [path/to/gpu_config.json]"
    exit 1
fi

echo "🔧 Debug Config Generation"
echo "========================="
echo "📄 Using config: $JSON_FILE"
echo ""
echo "📊 Configuration:"
cat "$JSON_FILE" | python3 -m json.tool
echo ""
echo "🏗️  Generating files..."

# Run the generator with the JSON config
python3 -m builder.generator "$(cat "$JSON_FILE")"

echo ""
echo "✅ Generated files in: builder/built/"
echo ""
echo "📄 Files created:"
ls -la builder/built/

echo ""
echo "📊 Generated Configuration Summary:"
echo "──────────────────────────────────"
# Count instances
INSTANCE_COUNT=$(grep -c "polyllama[0-9]:" builder/built/docker-compose.yml 2>/dev/null || echo "0")
GPU_INSTANCES=$(grep -B5 "CUDA_VISIBLE_DEVICES" builder/built/docker-compose.yml | grep "polyllama[0-9]:" | wc -l | tr -d ' ')
CPU_INSTANCES=$((INSTANCE_COUNT - GPU_INSTANCES))
echo "  Total instances: $INSTANCE_COUNT"
echo "  GPU instances:   $GPU_INSTANCES"
echo "  CPU instances:   $CPU_INSTANCES"
echo ""
echo "To inspect the generated files:"
echo "  - Docker Compose: cat builder/built/docker-compose.yml"
echo "  - Nginx Config:   cat builder/built/nginx.conf"