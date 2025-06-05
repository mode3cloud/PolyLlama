#!/usr/bin/env python3
"""
Test suite for PolyLlama dynamic compose and nginx generation
Tests various GPU configurations to ensure correct file generation
"""

import json
import sys
import subprocess
import tempfile
import os
from pathlib import Path
import yaml
import re


class PolyLlamaGenerationTest:
    """Test class for PolyLlama file generation"""

    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.builder_dir = self.root_dir / "builder"
        self.test_results = []

    def run_generation(self, gpu_config, test_name):
        """Run the generation script with given GPU config"""
        print(f"\n🧪 Running test: {test_name}")
        print(f"   GPU Config: {gpu_config}")

        # Run the generation script
        cmd = [
            "python3",
            str(self.builder_dir / "generator.py"),
            json.dumps(gpu_config),
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.root_dir
            )
            if result.returncode != 0:
                raise Exception(f"Generation failed: {result.stderr}")

            print(f"   ✅ Generation completed: {result.stdout.strip()}")
            return True
        except Exception as e:
            print(f"   ❌ Generation failed: {e}")
            return False

    def validate_compose_file(self, expected_instances, expected_instance_count):
        """Validate the generated docker-compose.yml file"""
        compose_file = self.root_dir / "runtime/docker-compose.yml"

        if not compose_file.exists():
            return False, "Compose file not generated"

        try:
            with open(compose_file, "r") as f:
                compose_content = yaml.safe_load(f)

            # Check services
            services = compose_content.get("services", {})

            # Check that expected instances exist
            for i in range(1, expected_instances + 1):
                instance_name = f"polyllama{i}"
                if instance_name not in services:
                    return False, f"Missing service: {instance_name}"

            # Check that no extra instances exist
            polyllama_services = [
                s for s in services.keys() if s.startswith("polyllama")
            ]
            if len(polyllama_services) != expected_instances:
                return (
                    False,
                    f"Expected {expected_instances} polyllama services, found {len(polyllama_services)}",
                )

            # Check router service has correct instance count
            router_service = services.get("router", {})
            router_env = router_service.get("environment", [])

            instance_count_found = False
            for env_var in router_env:
                if isinstance(env_var, str) and env_var.startswith(
                    "OLLAMA_INSTANCE_COUNT="
                ):
                    actual_count = int(env_var.split("=")[1])
                    if actual_count != expected_instance_count:
                        return (
                            False,
                            f"Wrong instance count: expected {expected_instance_count}, got {actual_count}",
                        )
                    instance_count_found = True
                    break

            if not instance_count_found:
                return False, "OLLAMA_INSTANCE_COUNT not found in router environment"

            return True, "Compose file validation passed"

        except Exception as e:
            return False, f"Error validating compose file: {e}"

    def validate_nginx_file(self, expected_instances):
        """Validate the generated nginx.conf file"""
        nginx_file = self.root_dir / "runtime/router/nginx.conf"

        if not nginx_file.exists():
            return False, "Nginx file not generated"

        try:
            with open(nginx_file, "r") as f:
                nginx_content = f.read()

            # Check upstream block contains correct servers
            upstream_pattern = r"upstream polyllama_backend \{[^}]*\}"
            upstream_match = re.search(upstream_pattern, nginx_content, re.DOTALL)

            if not upstream_match:
                return False, "polyllama_backend upstream block not found"

            upstream_block = upstream_match.group(0)

            # Check that expected servers are present
            for i in range(1, expected_instances + 1):
                server_pattern = f"server polyllama{i}:11434"
                if server_pattern not in upstream_block:
                    return False, f"Missing upstream server: polyllama{i}"

            # Check that no extra servers exist
            server_count = len(re.findall(r"server polyllama\d+:11434", upstream_block))
            if server_count != expected_instances:
                return (
                    False,
                    f"Expected {expected_instances} upstream servers, found {server_count}",
                )

            return True, "Nginx file validation passed"

        except Exception as e:
            return False, f"Error validating nginx file: {e}"

    def validate_gpu_assignments(self, gpu_config):
        """Validate GPU assignments in compose file match the config"""
        compose_file = self.root_dir / "runtime/docker-compose.yml"

        try:
            with open(compose_file, "r") as f:
                compose_content = yaml.safe_load(f)

            services = compose_content.get("services", {})
            gpu_groups = gpu_config.get("gpu_groups", [])

            if not gpu_groups:
                # CPU-only configuration
                polyllama1 = services.get("polyllama1", {})
                environment = polyllama1.get("environment", [])

                # Should not have CUDA_VISIBLE_DEVICES for CPU-only
                for env_var in environment:
                    if isinstance(env_var, str) and env_var.startswith(
                        "CUDA_VISIBLE_DEVICES="
                    ):
                        return (
                            False,
                            "CPU-only config should not have CUDA_VISIBLE_DEVICES",
                        )

                # Should not have GPU reservations
                deploy = polyllama1.get("deploy", {})
                resources = deploy.get("resources", {})
                reservations = resources.get("reservations", {})
                devices = reservations.get("devices", [])

                if devices:
                    return (
                        False,
                        "CPU-only config should not have GPU device reservations",
                    )

                return True, "CPU-only GPU assignment validation passed"

            # GPU configuration validation
            for i, group in enumerate(gpu_groups):
                instance_name = f"polyllama{i + 1}"
                service = services.get(instance_name, {})
                environment = service.get("environment", [])

                expected_gpus = ",".join(map(str, group["indices"]))

                # Check CUDA_VISIBLE_DEVICES
                cuda_devices_found = False
                for env_var in environment:
                    if isinstance(env_var, str) and env_var.startswith(
                        "CUDA_VISIBLE_DEVICES="
                    ):
                        actual_gpus = env_var.split("=")[1]
                        if actual_gpus != expected_gpus:
                            return (
                                False,
                                f"{instance_name}: expected GPUs {expected_gpus}, got {actual_gpus}",
                            )
                        cuda_devices_found = True
                        break

                if not cuda_devices_found:
                    return False, f"{instance_name}: CUDA_VISIBLE_DEVICES not found"

                # Check GPU reservations exist
                deploy = service.get("deploy", {})
                resources = deploy.get("resources", {})
                reservations = resources.get("reservations", {})
                devices = reservations.get("devices", [])

                gpu_reservation_found = False
                for device in devices:
                    if device.get("driver") == "nvidia" and "gpu" in device.get(
                        "capabilities", []
                    ):
                        gpu_reservation_found = True
                        break

                if not gpu_reservation_found:
                    return False, f"{instance_name}: GPU device reservation not found"

            return True, "GPU assignment validation passed"

        except Exception as e:
            return False, f"Error validating GPU assignments: {e}"

    def run_test(
        self, gpu_config, test_name, expected_instances, expected_instance_count=None
    ):
        """Run a complete test with validation"""
        if expected_instance_count is None:
            expected_instance_count = expected_instances

        success = True
        messages = []

        # Run generation
        if not self.run_generation(gpu_config, test_name):
            success = False
            messages.append("Generation failed")
        else:
            # Validate compose file
            compose_valid, compose_msg = self.validate_compose_file(
                expected_instances, expected_instance_count
            )
            if not compose_valid:
                success = False
                messages.append(f"Compose validation: {compose_msg}")
            else:
                messages.append(f"Compose validation: {compose_msg}")

            # Validate nginx file
            nginx_valid, nginx_msg = self.validate_nginx_file(expected_instances)
            if not nginx_valid:
                success = False
                messages.append(f"Nginx validation: {nginx_msg}")
            else:
                messages.append(f"Nginx validation: {nginx_msg}")

            # Validate GPU assignments
            gpu_valid, gpu_msg = self.validate_gpu_assignments(gpu_config)
            if not gpu_valid:
                success = False
                messages.append(f"GPU validation: {gpu_msg}")
            else:
                messages.append(f"GPU validation: {gpu_msg}")

        result = {"test_name": test_name, "success": success, "messages": messages}

        self.test_results.append(result)

        if success:
            print(f"   ✅ Test passed: {test_name}")
        else:
            print(f"   ❌ Test failed: {test_name}")
            for msg in messages:
                print(f"      - {msg}")

        return success


# Global test instance
tester = PolyLlamaGenerationTest()


def two_gpu_groups():
    """Test two GPU groups configuration"""
    assert tester.run_test(
        gpu_config={
            "gpu_groups": [
                {"name": "RTX 4090", "indices": [0, 1, 2]},
                {"name": "RTX 6000 Ada", "indices": [3]},
            ]
        },
        test_name="Two GPU Groups (4090 + 6000)",
        expected_instances=2,
    )


def three_gpu_groups():
    """Test three GPU groups configuration"""
    assert tester.run_test(
        gpu_config={
            "gpu_groups": [
                {"name": "RTX 4090", "indices": [0]},
                {"name": "RTX 3090", "indices": [1]},
                {"name": "RTX 6000", "indices": [2]},
            ]
        },
        test_name="Three GPU Groups (individual)",
        expected_instances=3,
    )


def single_gpu_group():
    """Test single GPU group configuration"""
    assert tester.run_test(
        gpu_config={"gpu_groups": [{"name": "RTX 4090", "indices": [0, 1, 2, 3]}]},
        test_name="Single GPU Group (all GPUs)",
        expected_instances=1,
    )


def cpu_only():
    """Test CPU-only configuration"""
    assert tester.run_test(
        gpu_config={"gpu_groups": []},
        test_name="CPU-only configuration",
        expected_instances=1,
    )


def mixed_gpu_types():
    """Test mixed GPU types configuration"""
    assert tester.run_test(
        gpu_config={
            "gpu_groups": [
                {"name": "RTX 4090", "indices": [0, 1]},
                {"name": "RTX 3090", "indices": [2]},
                {"name": "RTX 6000", "indices": [3, 4]},
                {"name": "RTX A100", "indices": [5]},
            ]
        },
        test_name="Mixed GPU types (4 groups)",
        expected_instances=4,
    )


def large_configuration():
    """Test large configuration with 6 groups"""
    assert tester.run_test(
        gpu_config={
            "gpu_groups": [
                {"name": "RTX 4090", "indices": [0]},
                {"name": "RTX 4090", "indices": [1]},
                {"name": "RTX 3090", "indices": [2]},
                {"name": "RTX 3090", "indices": [3]},
                {"name": "RTX 6000", "indices": [4]},
                {"name": "RTX A100", "indices": [5]},
            ]
        },
        test_name="Large configuration (6 groups)",
        expected_instances=6,
    )


if __name__ == "__main__":
    # Run all tests when script is executed directly
    two_gpu_groups()
    three_gpu_groups()
    single_gpu_group()
    cpu_only()
    mixed_gpu_types()
    large_configuration()
    
    # Print summary
    print("\n📊 Test Summary:")
    print("="*50)
    passed = sum(1 for r in tester.test_results if r['success'])
    failed = sum(1 for r in tester.test_results if not r['success'])
    total = len(tester.test_results)
    
    print(f"Total tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print("\n💔 Some tests failed. Please check the output above.")
        sys.exit(1)
