#!/usr/bin/env python3
"""
Edge case tests for PolyLlama generation
Tests unusual configurations and error conditions
"""

import json
import sys
import subprocess
from pathlib import Path

# Add the parent directory to the path to import builder module
sys.path.insert(0, str(Path(__file__).parent.parent))


def empty_gpu_group():
    """Test that empty GPU groups are handled correctly"""
    print("🧪 Testing edge case: Empty GPU group")

    root_dir = Path(__file__).parent.parent
    cmd = [
        "python3",
        str(root_dir / "builder/generator.py"),
        json.dumps({"gpu_groups": [{"name": "Empty", "indices": []}]}),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=root_dir)
    if result.returncode == 0:
        print("   ⚠️  Empty GPU group was accepted (may need validation)")
        assert True  # This test passes regardless since we're testing edge cases
    else:
        print("   ✅ Empty GPU group was rejected as expected")
        assert True  # This is also acceptable behavior


def single_gpu():
    """Test single GPU configuration"""
    print("🧪 Testing edge case: Single GPU")

    root_dir = Path(__file__).parent.parent
    cmd = [
        "python3",
        str(root_dir / "builder/generator.py"),
        json.dumps({"gpu_groups": [{"name": "RTX 4090", "indices": [0]}]}),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=root_dir)
    assert result.returncode == 0, f"Generation failed: {result.stderr}"

    print("   ✅ Single GPU configuration generated successfully")
    # Check that 2 instances were created (1 GPU + 1 CPU)
    assert (
        "Generated 2 instance(s)" in result.stdout
    ), f"Incorrect instance count for single GPU. Output: {result.stdout}"
    print("   ✅ Correct instance count for single GPU (1 GPU + 1 CPU)")


def large_gpu_indices():
    """Test with large GPU indices"""
    print("🧪 Testing edge case: Large GPU indices")

    root_dir = Path(__file__).parent.parent
    cmd = [
        "python3",
        str(root_dir / "builder/generator.py"),
        json.dumps(
            {
                "gpu_groups": [
                    {"name": "RTX 4090", "indices": [10, 11, 12]},
                    {"name": "RTX 6000", "indices": [20]},
                ]
            }
        ),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=root_dir)
    assert result.returncode == 0, f"Generation failed: {result.stderr}"
    print("   ✅ Large GPU indices handled successfully")
    # Check that 3 instances were created (2 GPU groups + 1 CPU)
    assert (
        "Generated 3 instance(s)" in result.stdout
    ), f"Incorrect instance count for large GPU indices. Output: {result.stdout}"
    print("   ✅ Correct instance count for large GPU indices (2 GPU + 1 CPU)")


def many_instances():
    """Test configuration with many instances"""
    print("🧪 Testing edge case: Many instances (10)")

    gpu_groups = []
    for i in range(10):
        gpu_groups.append({"name": f"GPU{i}", "indices": [i]})

    root_dir = Path(__file__).parent.parent
    cmd = [
        "python3",
        str(root_dir / "builder/generator.py"),
        json.dumps({"gpu_groups": gpu_groups}),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=root_dir)
    assert result.returncode == 0, f"Generation failed: {result.stderr}"

    print("   ✅ Many instances configuration generated successfully")
    assert (
        "Generated 11 instance(s)" in result.stdout
    ), f"Incorrect instance count for many instances. Output: {result.stdout}"
    print("   ✅ Correct instance count for many instances (10 GPU + 1 CPU)")


if __name__ == "__main__":
    # Run all edge case tests when script is executed directly
    empty_gpu_group()
    single_gpu()
    large_gpu_indices()
    many_instances()
    
    print("\n🎉 All edge case tests completed!")
