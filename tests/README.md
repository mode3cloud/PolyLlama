# PolyLlama Generation Tests

This directory contains comprehensive tests for the PolyLlama dynamic configuration generation system.

## Overview

The test suite validates that the dynamic generation system correctly creates Docker Compose and Nginx configuration files based on different GPU hardware configurations.

## Test Scenarios

### 1. **Two GPU Groups** (`RTX 4090 + RTX 6000`)
- **Config**: RTX 4090 (GPUs 0,1,2) + RTX 6000 Ada (GPU 3)
- **Expected**: 2 polyllama instances with appropriate GPU assignments
- **Validates**: Multi-GPU group configuration with different GPU types

### 2. **Three GPU Groups** (Individual GPUs)
- **Config**: RTX 4090 (GPU 0) + RTX 3090 (GPU 1) + RTX 6000 (GPU 2)
- **Expected**: 3 polyllama instances, each with one GPU
- **Validates**: Individual GPU assignment per instance

### 3. **Single GPU Group** (All GPUs)
- **Config**: RTX 4090 (GPUs 0,1,2,3)
- **Expected**: 1 polyllama instance with all GPUs
- **Validates**: Single instance with multiple GPUs

### 4. **CPU-only Configuration**
- **Config**: No GPU groups (empty array)
- **Expected**: 1 polyllama instance with no GPU configuration
- **Validates**: Fallback to CPU-only mode

### 5. **Mixed GPU Types** (4 Groups)
- **Config**: Various GPU types with different counts per group
- **Expected**: 4 polyllama instances with appropriate assignments
- **Validates**: Complex mixed-hardware scenarios

### 6. **Large Configuration** (6 Groups)
- **Config**: 6 different GPU groups
- **Expected**: 6 polyllama instances
- **Validates**: Scaling to larger hardware configurations

## What Each Test Validates

### Docker Compose File (`generated-compose.yml`)
- ✅ Correct number of `polyllama{N}` services generated
- ✅ Proper `CUDA_VISIBLE_DEVICES` environment variables
- ✅ Appropriate GPU device reservations for GPU instances
- ✅ No GPU configuration for CPU-only mode
- ✅ Correct `OLLAMA_INSTANCE_COUNT` in router service
- ✅ Proper service dependencies

### Nginx Configuration (`generated-nginx.conf`)
- ✅ Correct `polyllama_backend` upstream pool
- ✅ Right number of upstream servers
- ✅ Proper server naming (`polyllama1:11434`, etc.)
- ✅ No extra or missing server entries

### GPU Assignments
- ✅ GPU indices match the configuration
- ✅ CPU-only mode has no GPU assignments
- ✅ Each instance gets the correct GPU subset
- ✅ Memory limits scale with GPU count

## Running the Tests

### Quick Run
```bash
./tests/run_tests.sh
```

### Manual Run
```bash
# Run all tests with pytest
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_generation.py

# Run specific test function
uv run pytest tests/test_generation.py::test_cpu_only

# Run tests with verbose output
uv run pytest tests/ -v

# Legacy standalone execution
python3 tests/test_generation.py
```

### Prerequisites
- Python 3.10+
- Dependencies managed with uv: `uv sync`
- Or manual install: `pip install pytest pyyaml`

## Test Output

The test suite provides detailed output:

```
🧪 Running test: Two GPU Groups (4090 + 6000)
   GPU Config: {'gpu_groups': [{'name': 'RTX 4090', 'indices': [0, 1, 2]}, {'name': 'RTX 6000 Ada', 'indices': [3]}]}
   ✅ Generation completed: Generated /path/to/generated-compose.yml and /path/to/generated-nginx.conf with 2 instance(s)
   ✅ Test passed: Two GPU Groups (4090 + 6000)
```

## File Structure

```
tests/
├── README.md           # This file
├── run_tests.sh        # Test runner script
├── test_generation.py  # Main test suite
└── test_edge_cases.py  # Edge case and stress tests
```

## Adding New Tests

To add a new test scenario:

1. Open `test_generation.py`
2. Add a new `tester.run_test()` call in the `main()` function
3. Specify the GPU configuration and expected results
4. Run the test suite to verify

Example:
```python
tester.run_test(
    gpu_config={
        "gpu_groups": [
            {"name": "RTX 5090", "indices": [0, 1]}
        ]
    },
    test_name="RTX 5090 Dual GPU",
    expected_instances=1
)
```

## Integration with CI/CD

These tests can be integrated into automated workflows:

```yaml
# Example GitHub Actions workflow
- name: Run PolyLlama Generation Tests
  run: |
    pip install pyyaml
    ./tests/run_tests.sh
```

## Troubleshooting

### Common Issues

1. **Missing PyYAML**: Install with `pip install pyyaml`
2. **Permission denied**: Make sure `run_tests.sh` is executable: `chmod +x tests/run_tests.sh`
3. **Generation fails**: Ensure the `builder/generate_compose.py` script is working correctly

### Debug Mode

To see detailed output from failed tests, check the generated files manually:
- `generated-compose.yml` - Docker Compose configuration
- `generated-nginx.conf` - Nginx configuration

### Expected vs Actual

The tests compare:
- Number of services vs expected instances
- GPU assignments vs configuration
- Environment variables vs expected values
- File existence and structure