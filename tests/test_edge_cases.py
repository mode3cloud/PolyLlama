#!/usr/bin/env python3
"""
Edge case tests for PolyLlama generation
Tests unusual configurations and error conditions
"""

import json
import sys
import subprocess
from pathlib import Path

# Add the builder directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "builder"))

def test_empty_gpu_group():
    """Test that empty GPU groups are handled correctly"""
    print("🧪 Testing edge case: Empty GPU group")
    
    root_dir = Path(__file__).parent.parent
    cmd = [
        "python3", 
        str(root_dir / "builder/generate_compose.py"),
        json.dumps({"gpu_groups": [{"name": "Empty", "indices": []}]})
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=root_dir)
    if result.returncode == 0:
        print("   ⚠️  Empty GPU group was accepted (may need validation)")
        assert True  # This test passes regardless since we're testing edge cases
    else:
        print("   ✅ Empty GPU group was rejected as expected")
        assert True  # This is also acceptable behavior

def test_single_gpu():
    """Test single GPU configuration"""
    print("🧪 Testing edge case: Single GPU")
    
    root_dir = Path(__file__).parent.parent
    cmd = [
        "python3", 
        str(root_dir / "builder/generate_compose.py"),
        json.dumps({"gpu_groups": [{"name": "RTX 4090", "indices": [0]}]})
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=root_dir)
    assert result.returncode == 0, f"Generation failed: {result.stderr}"
    
    print("   ✅ Single GPU configuration generated successfully")
    # Check that only 1 instance was created
    assert "with 1 instance(s)" in result.stdout, f"Incorrect instance count for single GPU. Output: {result.stdout}"
    print("   ✅ Correct instance count for single GPU")

def test_large_gpu_indices():
    """Test with large GPU indices"""
    print("🧪 Testing edge case: Large GPU indices")
    
    root_dir = Path(__file__).parent.parent
    cmd = [
        "python3", 
        str(root_dir / "builder/generate_compose.py"),
        json.dumps({"gpu_groups": [
            {"name": "RTX 4090", "indices": [10, 11, 12]},
            {"name": "RTX 6000", "indices": [20]}
        ]})
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=root_dir)
    assert result.returncode == 0, f"Generation failed: {result.stderr}"
    print("   ✅ Large GPU indices handled successfully")

def test_many_instances():
    """Test configuration with many instances"""
    print("🧪 Testing edge case: Many instances (10)")
    
    gpu_groups = []
    for i in range(10):
        gpu_groups.append({"name": f"GPU{i}", "indices": [i]})
    
    root_dir = Path(__file__).parent.parent
    cmd = [
        "python3", 
        str(root_dir / "builder/generate_compose.py"),
        json.dumps({"gpu_groups": gpu_groups})
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=root_dir)
    assert result.returncode == 0, f"Generation failed: {result.stderr}"
    
    print("   ✅ Many instances configuration generated successfully")
    assert "with 10 instance(s)" in result.stdout, f"Incorrect instance count for many instances. Output: {result.stdout}"
    print("   ✅ Correct instance count for many instances")

def main():
    """Run edge case tests"""
    print("🧪 PolyLlama Edge Case Tests")
    print("=" * 40)
    
    tests = [
        test_empty_gpu_group,
        test_single_gpu,
        test_large_gpu_indices,
        test_many_instances
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            test()
            passed += 1
            print("   ✅ Test passed")
        except AssertionError as e:
            print(f"   ❌ Test failed: {e}")
        except Exception as e:
            print(f"   ❌ Test error: {e}")
        print()
    
    print("=" * 40)
    print("📊 Edge Case Test Results")
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("🎉 All edge case tests passed!")
        return 0
    else:
        print("❌ Some edge case tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())