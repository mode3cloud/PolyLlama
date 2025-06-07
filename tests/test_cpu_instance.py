"""
Test suite for verifying CPU instance is always present and last
"""

import pytest
from pathlib import Path

from builder.generator import ComposeGenerator


@pytest.fixture
def generator():
    """Create a ComposeGenerator instance for testing"""
    root_dir = Path(__file__).parent.parent
    return ComposeGenerator(root_dir)


class TestCPUInstance:
    """Test that CPU instance is always present and last"""

    def test_cpu_only_configuration(self, generator):
        """Test CPU-only configuration still has one CPU instance"""
        gpu_groups = []
        instances = generator._prepare_ollama_instances(gpu_groups)
        
        assert len(instances) == 1
        assert instances[0]["number"] == 1
        assert instances[0]["gpu_indices"] is None
        assert instances[0]["gpu_name"] == "CPU-only"
        assert instances[0]["gpu_count"] == 0

    def test_single_gpu_group_with_cpu(self, generator):
        """Test single GPU group has CPU instance as last"""
        gpu_groups = [
            {"name": "RTX 4090", "indices": [0, 1]}
        ]
        instances = generator._prepare_ollama_instances(gpu_groups)
        
        assert len(instances) == 2
        
        # First instance should be GPU
        assert instances[0]["number"] == 1
        assert instances[0]["gpu_indices"] == "0,1"
        assert instances[0]["gpu_name"] == "RTX 4090"
        assert instances[0]["gpu_count"] == 2
        
        # Last instance should be CPU
        assert instances[1]["number"] == 2
        assert instances[1]["gpu_indices"] is None
        assert instances[1]["gpu_name"] == "CPU-only"
        assert instances[1]["gpu_count"] == 0

    def test_multiple_gpu_groups_with_cpu(self, generator):
        """Test multiple GPU groups have CPU instance as last"""
        gpu_groups = [
            {"name": "RTX 4090", "indices": [0, 1]},
            {"name": "RTX 3090", "indices": [2, 3, 4]},
            {"name": "Tesla V100", "indices": [5]}
        ]
        instances = generator._prepare_ollama_instances(gpu_groups)
        
        assert len(instances) == 4  # 3 GPU groups + 1 CPU
        
        # First three should be GPU instances
        for i in range(3):
            assert instances[i]["number"] == i + 1
            assert instances[i]["gpu_indices"] is not None
            assert instances[i]["gpu_count"] > 0
        
        # Last instance should be CPU
        assert instances[3]["number"] == 4
        assert instances[3]["gpu_indices"] is None
        assert instances[3]["gpu_name"] == "CPU-only"
        assert instances[3]["gpu_count"] == 0

    def test_cpu_instance_always_last(self, generator):
        """Test that CPU instance is always the last one regardless of GPU count"""
        test_configs = [
            [],  # No GPUs
            [{"name": "GPU1", "indices": [0]}],  # 1 GPU
            [{"name": "GPU1", "indices": [0]}, {"name": "GPU2", "indices": [1]}],  # 2 groups
            [{"name": "GPU1", "indices": [0, 1, 2, 3, 4]}],  # 5 GPUs in one group
        ]
        
        for gpu_groups in test_configs:
            instances = generator._prepare_ollama_instances(gpu_groups)
            
            # Last instance should always be CPU
            last_instance = instances[-1]
            assert last_instance["gpu_indices"] is None
            assert last_instance["gpu_name"] == "CPU-only"
            assert last_instance["gpu_count"] == 0
            assert last_instance["number"] == len(instances)

    def test_instance_numbering_sequential(self, generator):
        """Test that instance numbers are sequential including CPU"""
        gpu_groups = [
            {"name": "RTX 4090", "indices": [0]},
            {"name": "RTX 3090", "indices": [1]},
        ]
        instances = generator._prepare_ollama_instances(gpu_groups)
        
        # Should have 3 instances total
        assert len(instances) == 3
        
        # Check sequential numbering
        for i, instance in enumerate(instances):
            assert instance["number"] == i + 1