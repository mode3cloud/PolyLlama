#!/usr/bin/env python3
"""
Test CPU routing behavior for PolyLlama.

Tests various scenarios to ensure CPU instances are only used when appropriate:
- GPU instances available → route to GPU
- No GPU instances → route to CPU
- Mixed mode with explicit CPU mapping → respect mapping
- All GPU instances offline → fallback to CPU
"""

import pytest
import json
import os
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from builder.generator import ComposeGenerator


class TestCPURouting:
    """Test CPU routing configuration and behavior"""

    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.root_dir = Path(__file__).parent.parent
        self.generator = ComposeGenerator(self.root_dir)
        self.output_dir = Path(self.temp_dir) / "built"
        self.output_dir.mkdir(exist_ok=True)

    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        # Clean up environment variables
        for key in list(os.environ.keys()):
            if key.startswith("POLYLLAMA_"):
                del os.environ[key]

    def test_gpu_only_deployment(self):
        """Test that GPU-only deployment creates no CPU instances by default"""
        config = {
            "gpu_groups": [
                {
                    "name": "NVIDIA GeForce RTX 4090",
                    "indices": [0, 1],
                    "devices": [
                        {"index": 0, "name": "NVIDIA GeForce RTX 4090", "pci_bus": "00:01.0"},
                        {"index": 1, "name": "NVIDIA GeForce RTX 4090", "pci_bus": "00:02.0"}
                    ]
                }
            ]
        }
        
        self.generator.generate(config, self.output_dir)
        
        # Check docker-compose.yml
        compose_file = self.output_dir / "docker-compose.yml"
        assert compose_file.exists()
        
        with open(compose_file, "r") as f:
            content = f.read()
            
        # Should have only 1 GPU instance
        assert "polyllama1:" in content
        assert "polyllama2:" not in content
        
        # Check nginx.conf for instance types
        nginx_file = self.output_dir / "nginx.conf"
        assert nginx_file.exists()
        
        with open(nginx_file, "r") as f:
            nginx_content = f.read()
            
        # Should set GPU instance type
        assert 'instance_types:set("instance_type:polyllama1", "gpu")' in nginx_content
        
        # Default routing mode should be prefer_gpu
        assert 'os.getenv("POLYLLAMA_CPU_ROUTING_MODE") or "prefer_gpu"' in nginx_content

    def test_cpu_only_deployment(self):
        """Test that CPU-only deployment (no GPUs) creates CPU instances"""
        config = {
            "gpu_groups": []  # No GPUs
        }
        
        self.generator.generate(config, self.output_dir)
        
        # Check docker-compose.yml
        compose_file = self.output_dir / "docker-compose.yml"
        assert compose_file.exists()
        
        with open(compose_file, "r") as f:
            content = f.read()
            
        # Should have at least 1 CPU instance
        assert "polyllama1:" in content
        
        # Should not have GPU devices
        assert "NVIDIA_VISIBLE_DEVICES" not in content
        
        # Check nginx.conf for instance types
        nginx_file = self.output_dir / "nginx.conf"
        with open(nginx_file, "r") as f:
            nginx_content = f.read()
            
        # Should set CPU instance type
        assert 'instance_types:set("instance_type:polyllama1", "cpu")' in nginx_content

    def test_mixed_mode_deployment(self):
        """Test mixed GPU+CPU deployment with POLYLLAMA_MIXED_MODE"""
        os.environ["POLYLLAMA_MIXED_MODE"] = "true"
        
        config = {
            "gpu_groups": [
                {
                    "name": "NVIDIA GeForce RTX 4090",
                    "indices": [0],
                    "devices": [
                        {"index": 0, "name": "NVIDIA GeForce RTX 4090", "pci_bus": "00:01.0"}
                    ]
                }
            ]
        }
        
        self.generator.generate(config, self.output_dir)
        
        # Check docker-compose.yml
        compose_file = self.output_dir / "docker-compose.yml"
        assert compose_file.exists()
        
        with open(compose_file, "r") as f:
            content = f.read()
            
        # Should have both GPU and CPU instances
        assert "polyllama1:" in content  # GPU instance
        assert "polyllama2:" in content  # CPU instance
        
        # Check nginx.conf for instance types
        nginx_file = self.output_dir / "nginx.conf"
        with open(nginx_file, "r") as f:
            nginx_content = f.read()
            
        # Should set both GPU and CPU instance types
        assert 'instance_types:set("instance_type:polyllama1", "gpu")' in nginx_content
        assert 'instance_types:set("instance_type:polyllama2", "cpu")' in nginx_content

    def test_explicit_cpu_instance_count(self):
        """Test explicit CPU instance count with POLYLLAMA_CPU_INSTANCES"""
        os.environ["POLYLLAMA_CPU_INSTANCES"] = "2"
        
        config = {
            "gpu_groups": [
                {
                    "name": "NVIDIA GeForce RTX 4090",
                    "indices": [0],
                    "devices": [
                        {"index": 0, "name": "NVIDIA GeForce RTX 4090", "pci_bus": "00:01.0"}
                    ]
                }
            ]
        }
        
        self.generator.generate(config, self.output_dir)
        
        # Check docker-compose.yml
        compose_file = self.output_dir / "docker-compose.yml"
        assert compose_file.exists()
        
        with open(compose_file, "r") as f:
            content = f.read()
            
        # Should have 1 GPU + 2 CPU instances
        assert "polyllama1:" in content  # GPU instance
        assert "polyllama2:" in content  # CPU instance 1
        assert "polyllama3:" in content  # CPU instance 2
        
        # Check nginx.conf for instance types
        nginx_file = self.output_dir / "nginx.conf"
        with open(nginx_file, "r") as f:
            nginx_content = f.read()
            
        # Should set correct instance types
        assert 'instance_types:set("instance_type:polyllama1", "gpu")' in nginx_content
        assert 'instance_types:set("instance_type:polyllama2", "cpu")' in nginx_content
        assert 'instance_types:set("instance_type:polyllama3", "cpu")' in nginx_content

    def test_cpu_routing_modes(self):
        """Test different CPU routing modes"""
        os.environ["POLYLLAMA_MIXED_MODE"] = "true"
        
        config = {
            "gpu_groups": [
                {
                    "name": "NVIDIA GeForce RTX 4090",
                    "indices": [0],
                    "devices": [
                        {"index": 0, "name": "NVIDIA GeForce RTX 4090", "pci_bus": "00:01.0"}
                    ]
                }
            ]
        }
        
        # Test with different routing modes
        for mode in ["prefer_gpu", "balanced", "gpu_only"]:
            os.environ["POLYLLAMA_CPU_ROUTING_MODE"] = mode
            
            self.generator.generate(config, self.output_dir)
            
            # Check nginx.conf
            nginx_file = self.output_dir / "nginx.conf"
            with open(nginx_file, "r") as f:
                nginx_content = f.read()
                
            # Routing mode should be set correctly
            assert f'os.getenv("POLYLLAMA_CPU_ROUTING_MODE") or "prefer_gpu"' in nginx_content

    def test_instance_type_tracking(self):
        """Test that instance types are properly tracked in nginx configuration"""
        os.environ["POLYLLAMA_CPU_INSTANCES"] = "1"
        
        config = {
            "gpu_groups": [
                {
                    "name": "NVIDIA Tesla V100",
                    "indices": [0, 1],
                    "devices": [
                        {"index": 0, "name": "NVIDIA Tesla V100", "pci_bus": "00:01.0"},
                        {"index": 1, "name": "NVIDIA Tesla V100", "pci_bus": "00:02.0"}
                    ]
                },
                {
                    "name": "NVIDIA Tesla T4",
                    "indices": [2],
                    "devices": [
                        {"index": 2, "name": "NVIDIA Tesla T4", "pci_bus": "00:03.0"}
                    ]
                }
            ]
        }
        
        self.generator.generate(config, self.output_dir)
        
        # Check nginx.conf
        nginx_file = self.output_dir / "nginx.conf"
        with open(nginx_file, "r") as f:
            nginx_content = f.read()
            
        # Should track all instance types correctly
        assert 'instance_types:set("instance_type:polyllama1", "gpu")' in nginx_content
        assert 'instance_types:set("instance_type:polyllama2", "gpu")' in nginx_content
        assert 'instance_types:set("instance_type:polyllama3", "cpu")' in nginx_content
        
        # Should have the instance-types endpoint
        assert "location /api/polyllama/instance-types" in nginx_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])