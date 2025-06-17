# CPU Routing Configuration

PolyLlama now supports advanced CPU routing modes and mixed GPU+CPU deployments. This document explains the available configuration options.

## Environment Variables

### POLYLLAMA_CPU_ROUTING_MODE

Controls how models are routed between GPU and CPU instances.

**Values:**
- `prefer_gpu` (default) - Routes models to GPU instances when available, falls back to CPU only when no GPU instances exist
- `balanced` - Treats all instances equally, distributing models based on load regardless of type
- `gpu_only` - Only routes to GPU instances, fails if no GPU instances are available

**Example:**
```bash
export POLYLLAMA_CPU_ROUTING_MODE=prefer_gpu
./polyllama.sh
```

### POLYLLAMA_CPU_INSTANCES

Specifies the number of CPU-only instances to create.

**Default:** `0` (no CPU instances unless no GPUs are detected)

**Example:**
```bash
export POLYLLAMA_CPU_INSTANCES=2
./polyllama.sh
```

### POLYLLAMA_MIXED_MODE

Enables mixed GPU+CPU deployment mode.

**Values:**
- `true` - Creates at least one CPU instance even when GPUs are available
- `false` (default) - Only creates CPU instances if explicitly requested or no GPUs detected

**Example:**
```bash
export POLYLLAMA_MIXED_MODE=true
./polyllama.sh
```

## Usage Scenarios

### Scenario 1: GPU-Only (Default)
```bash
# No configuration needed
./polyllama.sh
```
- Creates one instance per GPU group
- Routes all models to GPU instances
- No CPU instances created

### Scenario 2: Mixed GPU+CPU with GPU Preference
```bash
export POLYLLAMA_MIXED_MODE=true
export POLYLLAMA_CPU_ROUTING_MODE=prefer_gpu
./polyllama.sh
```
- Creates GPU instances + 1 CPU instance
- Routes models to GPUs first
- CPU instance used as overflow when GPUs are full

### Scenario 3: Balanced Mixed Deployment
```bash
export POLYLLAMA_MIXED_MODE=true
export POLYLLAMA_CPU_INSTANCES=2
export POLYLLAMA_CPU_ROUTING_MODE=balanced
./polyllama.sh
```
- Creates GPU instances + 2 CPU instances
- Distributes models evenly across all instances
- Good for mixed workloads

### Scenario 4: CPU-Only Fallback Testing
```bash
export POLYLLAMA_CPU_INSTANCES=1
export POLYLLAMA_CPU_ROUTING_MODE=prefer_gpu
./polyllama.sh
```
- Creates GPU instances + 1 CPU instance
- Useful for testing CPU fallback behavior

## Routing Logic Details

### prefer_gpu Mode
1. New models are assigned to the least-loaded GPU instance
2. If no GPU instances exist, assigns to least-loaded CPU instance
3. Existing model mappings are preserved

### balanced Mode
1. New models are assigned to the least-loaded instance of any type
2. No preference given to GPU or CPU
3. Results in even distribution across all instances

### gpu_only Mode
1. New models are only assigned to GPU instances
2. Returns error if no GPU instances are available
3. Use for GPU-exclusive workloads

## Monitoring

Use the new API endpoint to check instance types and routing mode:

```bash
curl http://localhost:11434/api/polyllama/instance-types
```

Response:
```json
{
  "instances": [
    {"name": "polyllama1", "type": "gpu"},
    {"name": "polyllama2", "type": "gpu"},
    {"name": "polyllama3", "type": "cpu"}
  ],
  "cpu_routing_mode": "prefer_gpu",
  "timestamp": 1234567890
}
```

## Best Practices

1. **Production Deployments**: Use `prefer_gpu` mode (default) for optimal performance
2. **Development/Testing**: Use `balanced` mode to test both GPU and CPU code paths
3. **Resource Constraints**: Use mixed mode with CPU instances for overflow capacity
4. **Cost Optimization**: Use balanced mode to utilize cheaper CPU instances for suitable workloads