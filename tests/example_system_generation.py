#!/usr/bin/env python3
"""
Local system template generation validation.

This validates that the template generation system produces
exactly the same output for the local system configuration as
the artifacts saved in the repository.
"""

import json
import subprocess
import tempfile
import os
from pathlib import Path
import pytest


def example_system_template_generation():
    """Test that template generation matches expected artifacts for local system."""

    # Get the project root directory
    project_root = Path(__file__).parent.parent
    builder_dir = project_root / "builder"
    test_artifacts_dir = project_root / "tests" / "test_artifacts"

    # Load the local system GPU configuration
    gpu_config_path = test_artifacts_dir / "example_system_gpu_config.json"
    with open(gpu_config_path, "r") as f:
        gpu_config = json.load(f)

    # Create a temporary directory for generated files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Change to builder directory to run the generation script
        original_cwd = os.getcwd()
        try:
            os.chdir(builder_dir)

            # Run the generation script with the local system GPU config
            gpu_config_json = json.dumps(gpu_config)
            result = subprocess.run(
                ["python3", "generator.py", gpu_config_json],
                capture_output=True,
                text=True,
                cwd=builder_dir,
            )

            # Check that the generation script ran successfully
            assert result.returncode == 0, f"Generation script failed: {result.stderr}"

            # The script outputs to runtime/ directory, so read from there
            runtime_dir = builder_dir.parent / "runtime"
            generated_compose_path = runtime_dir / "docker-compose.yml"
            generated_nginx_path = runtime_dir / "router" / "nginx.conf"

            # Read generated files
            with open(generated_compose_path, "r") as f:
                generated_compose = f.read()

            with open(generated_nginx_path, "r") as f:
                generated_nginx = f.read()

        finally:
            os.chdir(original_cwd)

    # Load expected artifacts
    expected_compose_path = test_artifacts_dir / "example_system_docker-compose.yml"
    expected_nginx_path = test_artifacts_dir / "example_system_nginx.conf"

    with open(expected_compose_path, "r") as f:
        expected_compose = f.read()

    with open(expected_nginx_path, "r") as f:
        expected_nginx = f.read()

    # Compare generated content with expected artifacts
    assert generated_compose == expected_compose, (
        "Generated docker-compose.yml does not match expected artifact. "
        "This could indicate a regression in template generation."
    )

    assert generated_nginx == expected_nginx, (
        "Generated nginx.conf does not match expected artifact. "
        "This could indicate a regression in template generation."
    )

    print("✅ Local system template generation matches expected artifacts")


def example_system_gpu_config_validity():
    """Validate that the local system GPU config is valid."""

    test_artifacts_dir = Path(__file__).parent.parent / "tests" / "test_artifacts"
    gpu_config_path = test_artifacts_dir / "example_system_gpu_config.json"

    with open(gpu_config_path, "r") as f:
        gpu_config = json.load(f)

    # Validate structure
    assert "gpu_groups" in gpu_config, "GPU config must have 'gpu_groups' key"
    assert isinstance(gpu_config["gpu_groups"], list), "gpu_groups must be a list"
    assert len(gpu_config["gpu_groups"]) > 0, "Must have at least one GPU group"

    # Validate each group
    for i, group in enumerate(gpu_config["gpu_groups"]):
        assert "name" in group, f"Group {i} missing 'name' field"
        assert "indices" in group, f"Group {i} missing 'indices' field"
        assert isinstance(group["name"], str), f"Group {i} name must be string"
        assert isinstance(group["indices"], list), f"Group {i} indices must be list"
        assert len(group["indices"]) > 0, f"Group {i} must have at least one GPU index"

        # Validate indices are integers
        for idx in group["indices"]:
            assert isinstance(idx, int), f"Group {i} index {idx} must be integer"
            assert idx >= 0, f"Group {i} index {idx} must be non-negative"

    # Check for unique GPU indices across all groups
    all_indices = []
    for group in gpu_config["gpu_groups"]:
        all_indices.extend(group["indices"])

    assert len(all_indices) == len(
        set(all_indices)
    ), "GPU indices must be unique across groups"

    print("✅ Local system GPU config is valid")


def artifacts_exist():
    """Validate that all required artifacts exist."""

    test_artifacts_dir = Path(__file__).parent.parent / "tests" / "test_artifacts"

    required_files = [
        "example_system_gpu_config.json",
        "example_system_docker-compose.yml",
        "example_system_nginx.conf",
    ]

    for filename in required_files:
        file_path = test_artifacts_dir / filename
        assert file_path.exists(), f"Artifact {filename} not found at {file_path}"
        assert file_path.is_file(), f"Artifact {filename} is not a file"
        assert file_path.stat().st_size > 0, f"Artifact {filename} is empty"

    print("✅ All artifacts exist and are non-empty")


def generated_compose_structure():
    """Validate that generated docker-compose.yml has correct structure for local system."""

    test_artifacts_dir = Path(__file__).parent.parent / "tests" / "test_artifacts"
    compose_path = test_artifacts_dir / "example_system_docker-compose.yml"

    with open(compose_path, "r") as f:
        compose_content = f.read()

    # Check for project name
    assert "name: mode3ai_polyllama" in compose_content, "Missing project name"

    # Check for expected services
    expected_services = ["openwebui:", "olah:", "polyllama1:", "polyllama2:", "router:"]

    for service in expected_services:
        assert service in compose_content, f"Missing service: {service}"

    # Check for expected GPU configurations based on local system
    # Instance 1: RTX 6000 Ada (GPU 3)
    assert (
        "CUDA_VISIBLE_DEVICES=3" in compose_content
    ), "Missing GPU 3 assignment for polyllama1"

    # Instance 2: RTX 4090s (GPUs 0,1,2)
    assert (
        "CUDA_VISIBLE_DEVICES=0,1,2" in compose_content
    ), "Missing GPU 0,1,2 assignment for polyllama2"

    # Check for correct instance count in router environment
    assert (
        "OLLAMA_INSTANCE_COUNT=2" in compose_content
    ), "Missing or incorrect instance count"

    # Check for correct memory limits
    assert (
        "memory: 32g" in compose_content
    ), "Missing 32g memory limit for single GPU instance"
    assert (
        "memory: 96g" in compose_content
    ), "Missing 96g memory limit for 3-GPU instance"

    print("✅ Generated docker-compose.yml has correct structure for local system")


def generated_nginx_structure():
    """Validate that generated nginx.conf has correct structure for local system."""

    test_artifacts_dir = Path(__file__).parent.parent / "tests" / "test_artifacts"
    nginx_path = test_artifacts_dir / "example_system_nginx.conf"

    with open(nginx_path, "r") as f:
        nginx_content = f.read()

    # Check for upstream backend pool with correct instances
    assert (
        "upstream polyllama_backend" in nginx_content
    ), "Missing upstream backend pool"
    assert "server polyllama1:11434" in nginx_content, "Missing polyllama1 server"
    assert "server polyllama2:11434" in nginx_content, "Missing polyllama2 server"

    # Should not have polyllama3+ since we only have 2 instances for local system
    assert (
        "server polyllama3:11434" not in nginx_content
    ), "Should not have polyllama3 for 2-instance config"

    # Check for correct instance count in Lua code
    assert 'or "2"' in nginx_content, "Missing correct default instance count in Lua"

    # Check for essential nginx configuration sections
    essential_sections = [
        "lua_shared_dict model_mappings 10m;",
        "location /api/ui/instance-status",
        "location ~ ^/api/(generate|chat|embeddings)$",
        "location /api/ui/instance-count",
    ]

    for section in essential_sections:
        assert section in nginx_content, f"Missing essential nginx section: {section}"

    print("✅ Generated nginx.conf has correct structure for local system")


if __name__ == "__main__":
    # Run validation when script is executed directly
    artifacts_exist()
    example_system_gpu_config_validity()
    generated_compose_structure()
    generated_nginx_structure()
    example_system_template_generation()
    print("🎉 All local system generation validations passed!")
