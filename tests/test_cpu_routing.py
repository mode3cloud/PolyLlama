#!/usr/bin/env python3
"""
Test CPU routing configuration for PolyLlama
"""

import json
import os
import re
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from builder.generator import ComposeGenerator
from builder.detector import GPUDetector


def test_cpu_routing_scenarios():
    """Test various CPU routing scenarios"""
    
    # Initialize generator
    root_dir = Path(__file__).parent.parent
    generator = ComposeGenerator(root_dir)
    output_dir = Path(__file__).parent / "test_output"
    output_dir.mkdir(exist_ok=True)
    
    print("Testing CPU Routing Scenarios\n")
    
    # Scenario 1: GPU-only (default)
    print("Scenario 1: GPU-only (default)")
    os.environ.pop("POLYLLAMA_CPU_INSTANCES", None)
    os.environ.pop("POLYLLAMA_MIXED_MODE", None)
    
    gpu_groups = [
        {"name": "RTX 4090", "indices": [0, 1], "devices": []},
        {"name": "RTX 3090", "indices": [2, 3], "devices": []}
    ]
    
    config = {"gpu_groups": gpu_groups}
    generator.generate(config, output_dir)
    
    with open(output_dir / "docker-compose.yml") as f:
        content = f.read()
        # Count actual service definitions
        service_count = len(re.findall(r'^  polyllama\d+:', content, re.MULTILINE))
        gpu_count = content.count("CUDA_VISIBLE_DEVICES")
        cpu_count = service_count - gpu_count
        print(f"  Total instances: {service_count}")
        print(f"  GPU instances: {gpu_count}")
        print(f"  CPU instances: {cpu_count}")
        assert gpu_count == 2, "Should have 2 GPU instances"
        assert cpu_count == 0, "Should have 0 CPU instances"
    
    # Scenario 2: Mixed mode
    print("\nScenario 2: Mixed mode with 1 CPU instance")
    os.environ["POLYLLAMA_MIXED_MODE"] = "true"
    
    generator.generate(config, output_dir)
    
    with open(output_dir / "docker-compose.yml") as f:
        content = f.read()
        service_count = len(re.findall(r'^  polyllama\d+:', content, re.MULTILINE))
        gpu_count = content.count("CUDA_VISIBLE_DEVICES")
        cpu_count = service_count - gpu_count
        print(f"  Total instances: {service_count}")
        print(f"  GPU instances: {gpu_count}")
        print(f"  CPU instances: {cpu_count}")
        assert gpu_count == 2, "Should have 2 GPU instances"
        assert cpu_count == 1, "Should have 1 CPU instance"
    
    # Scenario 3: Explicit CPU instances
    print("\nScenario 3: Explicit 2 CPU instances")
    os.environ["POLYLLAMA_MIXED_MODE"] = "false"
    os.environ["POLYLLAMA_CPU_INSTANCES"] = "2"
    
    generator.generate(config, output_dir)
    
    with open(output_dir / "docker-compose.yml") as f:
        content = f.read()
        service_count = len(re.findall(r'^  polyllama\d+:', content, re.MULTILINE))
        gpu_count = content.count("CUDA_VISIBLE_DEVICES")
        cpu_count = service_count - gpu_count
        print(f"  Total instances: {service_count}")
        print(f"  GPU instances: {gpu_count}")
        print(f"  CPU instances: {cpu_count}")
        assert gpu_count == 2, "Should have 2 GPU instances"
        assert cpu_count == 2, "Should have 2 CPU instances"
    
    # Scenario 4: CPU-only (no GPUs)
    print("\nScenario 4: CPU-only (no GPUs detected)")
    os.environ.pop("POLYLLAMA_CPU_INSTANCES", None)
    os.environ.pop("POLYLLAMA_MIXED_MODE", None)
    
    config = {"gpu_groups": []}
    generator.generate(config, output_dir)
    
    with open(output_dir / "docker-compose.yml") as f:
        content = f.read()
        service_count = len(re.findall(r'^  polyllama\d+:', content, re.MULTILINE))
        gpu_count = content.count("CUDA_VISIBLE_DEVICES")
        cpu_count = service_count - gpu_count
        print(f"  Total instances: {service_count}")
        print(f"  GPU instances: {gpu_count}")
        print(f"  CPU instances: {cpu_count}")
        assert gpu_count == 0, "Should have 0 GPU instances"
        assert cpu_count == 1, "Should have at least 1 CPU instance"
    
    # Scenario 5: CPU-only with multiple instances
    print("\nScenario 5: CPU-only with 3 instances")
    os.environ["POLYLLAMA_CPU_INSTANCES"] = "3"
    
    config = {"gpu_groups": []}
    generator.generate(config, output_dir)
    
    with open(output_dir / "docker-compose.yml") as f:
        content = f.read()
        service_count = len(re.findall(r'^  polyllama\d+:', content, re.MULTILINE))
        gpu_count = content.count("CUDA_VISIBLE_DEVICES")
        cpu_count = service_count - gpu_count
        print(f"  Total instances: {service_count}")
        print(f"  CPU instances: {cpu_count}")
        assert cpu_count == 3, "Should have 3 CPU instances"
    
    # Test nginx.conf generation with instance types
    print("\nTesting nginx.conf instance type configuration...")
    with open(output_dir / "nginx.conf") as f:
        content = f.read()
        # Check for instance type settings
        assert 'instance_types:set("instance_type:polyllama' in content, "Should set instance types"
        # Check if we have proper instance type setting in the Lua code
        assert '"gpu" if instance.gpu_indices else "cpu"' in content, "Should have instance type logic"
    
    print("\n✅ All CPU routing tests passed!")
    
    # Clean up
    import shutil
    shutil.rmtree(output_dir)


if __name__ == "__main__":
    test_cpu_routing_scenarios()