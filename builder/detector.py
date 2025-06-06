"""
GPU detection module for PolyLlama
"""

import os
import subprocess
from collections import defaultdict
from typing import List, Dict, Optional


class GPUDetector:
    """Detects and groups GPUs by type"""

    def __init__(self):
        self.gpu_groups = []

    def detect_gpu_groups(self) -> List[Dict]:
        """
        Detect GPUs and group them by type

        Returns:
            List of GPU groups, each with 'name' and 'indices'
        """
        gpu_info = self._get_gpu_info()

        if not gpu_info:
            print("⚠️  No GPUs detected or NVIDIA runtime unavailable")
            return []

        # Group GPUs by type
        gpu_type_groups = defaultdict(list)
        gpu_devices_by_type = defaultdict(list)

        print("🔍 Detected GPUs using nvidia-smi (PCI bus order):")
        for gpu in gpu_info:
            index = gpu["index"]
            name = gpu["name"]
            pci_bus = gpu["pci_bus"]

            print(f"  GPU {index}: {name} ({pci_bus})")
            gpu_type_groups[name].append(index)
            gpu_devices_by_type[name].append(
                {"index": index, "name": name, "pci_bus": pci_bus}
            )

        # Convert to list format
        gpu_groups = []
        for gpu_type, indices in gpu_type_groups.items():
            gpu_groups.append(
                {
                    "name": gpu_type,
                    "indices": sorted(indices),  # Ensure consistent ordering
                    "devices": sorted(
                        gpu_devices_by_type[gpu_type], key=lambda x: x["index"]
                    ),
                }
            )

        print()
        print("📊 GPU Grouping Results:")
        if not gpu_groups:
            print("  No GPU groups found - will use CPU-only configuration")
        else:
            for i, group in enumerate(gpu_groups, 1):
                indices_str = ",".join(map(str, group["indices"]))
                count = len(group["indices"])
                print(
                    f"  Group {i}: {group['name']} (GPUs: {indices_str}) - {count} GPU(s)"
                )

        return gpu_groups

    def _get_gpu_info(self) -> Optional[List[Dict]]:
        """
        Get GPU information using nvidia-smi

        Returns:
            List of GPU info dicts with 'index', 'name', and 'pci_bus'
        """
        # Try nvidia-smi directly first
        gpu_info = self._try_nvidia_smi()

        # If that fails, try through Docker
        if not gpu_info:
            gpu_info = self._try_docker_nvidia_smi()

        return gpu_info

    def _try_nvidia_smi(self) -> Optional[List[Dict]]:
        """Try to run nvidia-smi directly"""
        try:
            # Use CUDA_DEVICE_ORDER for consistent ordering
            env = dict(os.environ)
            env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"

            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,pci.bus_id",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )

            return self._parse_nvidia_smi_output(result.stdout)

        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _try_docker_nvidia_smi(self) -> Optional[List[Dict]]:
        """Try to run nvidia-smi through Docker"""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--gpus",
                    "all",
                    "nvidia/cuda:11.0-base",
                    "nvidia-smi",
                    "--query-gpu=index,name,pci.bus_id",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            return self._parse_nvidia_smi_output(result.stdout)

        except subprocess.CalledProcessError:
            return None

    def _parse_nvidia_smi_output(self, output: str) -> List[Dict]:
        """Parse nvidia-smi CSV output"""
        gpu_info = []

        for line in output.strip().split("\n"):
            if not line:
                continue

            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                gpu_info.append(
                    {"index": int(parts[0]), "name": parts[1], "pci_bus": parts[2]}
                )

        return gpu_info
