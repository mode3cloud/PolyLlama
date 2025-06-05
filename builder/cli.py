#!/usr/bin/env python3
"""
PolyLlama CLI - Main entry point for the polyllama command
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .detector import GPUDetector
from .generator import ComposeGenerator


class PolyLlamaCLI:
    """Main CLI class for PolyLlama"""

    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.built_dir = Path(__file__).parent / "built"
        self.compose_file = self.built_dir / "docker-compose.yml"
        self.log_file = self.built_dir / "polyllama-compose-build.log"

        # Ensure built directory exists
        self.built_dir.mkdir(exist_ok=True)

    def check_docker(self) -> bool:
        """Check if Docker is running"""
        try:
            subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            print("Error: Docker is not running or not accessible")
            print("Please start Docker and try again")
            return False

    def check_env_file(self):
        """Check and create .env file if needed"""
        env_file = self.root_dir / ".env"
        env_example = self.root_dir / ".env.example"

        if not env_file.exists():
            if env_example.exists():
                print("📄 .env file not found, copying from .env.example...")
                env_example.read_text()
                env_file.write_text(env_example.read_text())
                print("✅ Created .env file from .env.example")
                print("💡 You may want to edit .env to customize your configuration")
            else:
                print("⚠️  .env file not found and .env.example doesn't exist")
                print("   The stack will use default environment settings")

    def detect_and_generate(self, dev_mode: bool = False) -> Dict:
        """Detect hardware and generate configuration"""
        detector = GPUDetector()
        gpu_groups = detector.detect_gpu_groups()

        # Generate compose file
        generator = ComposeGenerator(self.root_dir)
        config = {"gpu_groups": gpu_groups}
        generator.generate(config, self.built_dir, dev_mode=dev_mode)

        # Calculate instance count
        instance_count = len(gpu_groups) if gpu_groups else 1

        return {
            "gpu_groups": gpu_groups,
            "instance_count": instance_count,
            "gpu_count": (
                sum(len(g["indices"]) for g in gpu_groups) if gpu_groups else 0
            ),
            "config_type": (
                f"dynamic-{len(gpu_groups)}-groups" if gpu_groups else "cpu-only"
            ),
            "dev_mode": dev_mode,
        }

    def print_banner(self):
        """Print the awesome PolyLlama ASCII banner"""
        print("")
        print("")
        print(
            "   \033[94m██████╗  ██████╗ ██╗  ██╗   ██╗██╗     ██╗      █████╗ ███╗   ███╗ █████╗\033[0m"
        )
        print(
            "   \033[94m██╔══██╗██╔═══██╗██║  ╚██╗ ██╔╝██║     ██║     ██╔══██╗████╗ ████║██╔══██╗\033[0m"
        )
        print(
            "   \033[94m██████╔╝██║   ██║██║   ╚████╔╝ ██║     ██║     ███████║██╔████╔██║███████║\033[0m"
        )
        print(
            "   \033[94m██╔═══╝ ██║   ██║██║    ╚██╔╝  ██║     ██║     ██╔══██║██║╚██╔╝██║██╔══██║\033[0m"
        )
        print(
            "   \033[94m██║     ╚██████╔╝███████╗██║   ███████╗███████╗██║  ██║██║ ╚═╝ ██║██║  ██║\033[0m"
        )
        print(
            "   \033[94m╚═╝      ╚═════╝ ╚══════╝╚═╝   ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝\033[0m"
        )
        print("")
        print(
            "   \033[92m🦙 Dynamic Multi-Instance Ollama Orchestration for Local AI Power\033[0m"
        )
        print("")
        print(
            "   \033[93m✨ Features:\033[0m"
        )
        print(
            "     \033[97m• Auto GPU Detection & Grouping  • Intelligent Load Balancing\033[0m"
        )
        print(
            "     \033[97m• Dynamic Docker Compose Generation  • Modern Web Interface\033[0m"
        )
        print("")
        print(
            "   \033[95m📖 Documentation & Source: https://github.com/mode3cloud/PolyLlama\033[0m"
        )
        print("")

    def launch(self, debug: bool = False, build: bool = False, dev_mode: bool = False):
        """Launch the PolyLlama stack"""
        if not self.check_docker():
            return 1

        self.check_env_file()
        self.print_banner()

        print("🚀 Starting dynamic Ollama stack deployment...")
        if dev_mode:
            print("🔧 Development mode enabled - Next.js app will run with hot reloading")
        print("")

        # Detect and generate configuration
        config = self.detect_and_generate(dev_mode=dev_mode)

        print("")
        print("🎯 Deployment Summary:")
        print(f"  GPUs detected: {config['gpu_count']}")
        print(f"  GPU groups: {len(config['gpu_groups'])}")
        print(f"  Ollama instances: {config['instance_count']}")
        print(f"  Generated file: {self.compose_file}")

        # Stop any existing services
        print("🛑 Stopping any existing services...")
        subprocess.run(
            [
                "docker-compose",
                "-f",
                str(self.compose_file),
                "down",
                "--remove-orphans",
            ],
            stderr=subprocess.DEVNULL,
        )

        # Pull latest images
        print("📦 Pulling latest images...")
        if debug:
            print("   Debug mode: showing output on console")
            subprocess.run(["docker-compose", "-f", str(self.compose_file), "pull"])
        else:
            print(f"   Output logged to: {self.log_file}")
            with open(self.log_file, "w") as log:
                subprocess.run(
                    ["docker-compose", "-f", str(self.compose_file), "pull"],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )

        # Build services
        print("🔨 Building services...")
        build_cmd = ["docker-compose", "-f", str(self.compose_file), "build"]
        if build:
            print("   Force rebuild: --no-cache enabled")
            build_cmd.append("--no-cache")

        if debug:
            print("   Debug mode: showing output on console")
            result = subprocess.run(build_cmd)
        else:
            print(
                f"   This may take a few minutes... output logged to: {self.log_file}"
            )
            with open(self.log_file, "a") as log:
                result = subprocess.run(build_cmd, stdout=log, stderr=subprocess.STDOUT)

        # Check if build was successful
        if result.returncode != 0:
            print("   ❌ Build failed - check {self.log_file} for details")
            print("")
            print("📋 Last 10 lines of build log:")
            with open(self.log_file, "r") as log:
                lines = log.readlines()
                for line in lines[-10:]:
                    print(line.rstrip())
            return 1
        else:
            print("   ✅ Build completed successfully")

        # Start services
        print("▶️  Starting services...")
        up_cmd = ["docker-compose", "-f", str(self.compose_file), "up", "-d"]
        if build:
            up_cmd.append("--build")
        subprocess.run(up_cmd)

        # Show status
        print("")
        print("✅ Dynamic Ollama stack launched successfully!")
        print(
            f"🎯 Configuration: {config['instance_count']} instance(s) across {len(config['gpu_groups'])} GPU group(s)"
        )
        print(f"🔍 Total GPUs: {config['gpu_count']}")
        print("")

        if config["gpu_groups"]:
            print("📊 Instance → GPU Mapping:")
            for i, group in enumerate(config["gpu_groups"], 1):
                indices_str = ",".join(map(str, group["indices"]))
                print(f"  polyllama{i} → {group['name']} (GPUs: {indices_str})")
            print("")

        print(
            "🌐+🤖 Polyllama Endpoint (UI and Ollama Router): http://localhost:11434/"
        )
        if dev_mode:
            print("💡 Edit files in stack/router/app/ for hot reloading")
        print("")
        print("📋 Service Status:")
        subprocess.run(["docker-compose", "-f", str(self.compose_file), "ps"])
        print("")
        print("💡 Commands:")
        print("  📜 View logs: ./polyllama.sh --logs")
        print("  🛑 Stop: ./polyllama.sh --stop")
        print("  📊 Status: ./polyllama.sh --status")
        print("  🔍 Detect: ./polyllama.sh --detect")
        print("")
        print(f"📄 Generated compose file: {self.compose_file}")
        print(f"📋 Compose Build log: {self.log_file}")
        print("")
        print("Thank you for using PolyLlama! 🦙")

        return 0

    def stop(self):
        """Stop all services"""
        if not self.check_docker():
            return 1

        print("🛑 Stopping Polyllama stack...")

        if self.compose_file.exists():
            print(f"  Stopping services from {self.compose_file}...")
            subprocess.run(
                [
                    "docker-compose",
                    "-f",
                    str(self.compose_file),
                    "down",
                    "--remove-orphans",
                ],
                stderr=subprocess.DEVNULL,
            )

        print("✅ All services stopped")
        return 0

    def logs(self):
        """Show logs from all services"""
        if not self.check_docker():
            return 1

        print("📜 Showing logs from all services...")

        if self.compose_file.exists():
            # Check if services are running
            result = subprocess.run(
                ["docker-compose", "-f", str(self.compose_file), "ps", "--services"],
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                print(f"  Logs from {self.compose_file}:")
                subprocess.run(
                    [
                        "docker-compose",
                        "-f",
                        str(self.compose_file),
                        "logs",
                        "--tail=50",
                        "-f",
                    ]
                )
                return 0

        print("❌ No running services found")
        return 1

    def status(self):
        """Show status of all services"""
        if not self.check_docker():
            return 1

        print("📊 Service Status:")

        if self.compose_file.exists():
            print("")
            print(f"  From {self.compose_file}:")
            result = subprocess.run(
                ["docker-compose", "-f", str(self.compose_file), "ps"],
                capture_output=True,
                text=True,
            )
            if "Up" in result.stdout:
                print(result.stdout)
            else:
                print("    No services running")
        return 0

    def detect(self):
        """Show detected hardware configuration"""
        print("🔍 Starting hardware detection...")
        print("")

        config = self.detect_and_generate()

        print("")
        print("📋 Final Configuration Summary:")
        print(f"  Total GPUs: {config['gpu_count']}")
        print(f"  GPU Groups: {len(config['gpu_groups'])}")
        print(f"  Ollama Instances: {config['instance_count']}")
        print(f"  Configuration: {config['config_type']}")
        print(f"  Generated file: {self.compose_file}")
        print("")

        if not config["gpu_groups"]:
            print("  🖥️  CPU-Only Configuration:")
            print("    - No GPUs detected or NVIDIA runtime unavailable")
            print("    - Will create 1 Ollama instance using CPU only")
            print("    - Suitable for smaller models and inference")
        else:
            print("  🎯 Dynamic GPU Configuration:")
            for i, group in enumerate(config["gpu_groups"], 1):
                indices = group["indices"]
                gpu_count = len(indices)
                indices_str = ",".join(map(str, indices))
                print(
                    f"    - Instance {i}: {group['name']} (GPUs: {indices_str}) - {gpu_count} GPU(s)"
                )
            print("    - Each group gets dedicated Ollama instance")
            print("    - OLLAMA_SCHED_SPREAD=1 for optimal GPU utilization")
            print("    - CUDA_DEVICE_ORDER=PCI_BUS_ID for consistent ordering")

        print("")
        print("📄 Generated Docker Compose Preview:")
        print("─────────────────────────────────────")
        with open(self.compose_file, "r") as f:
            lines = f.readlines()[:50]
            for line in lines:
                print(f"  {line.rstrip()}")
        print("  ...")
        print("─────────────────────────────────────")

        return 0


def main():
    """Main entry point for the CLI"""
    parser = argparse.ArgumentParser(
        description="PolyLlama - Dynamic multi-instance Ollama orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Hardware Detection:
  - Multiple GPU types → One instance per GPU type group
  - Single GPU type    → One instance with all GPUs
  - 0 GPUs            → CPU-only configuration

Examples:
  polyllama              # Auto-detect and launch
  polyllama --detect     # Show what would be detected
  polyllama --debug      # Launch with debug output on console
  polyllama --build      # Launch and force rebuild images
  polyllama --stop       # Stop all services
""",
    )

    parser.add_argument("--stop", action="store_true", help="Stop all services")

    parser.add_argument(
        "--logs", action="store_true", help="Show logs from all services"
    )

    parser.add_argument(
        "--status", action="store_true", help="Show status of all services"
    )

    parser.add_argument(
        "--detect", action="store_true", help="Show detected hardware configuration"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (show build output on console)",
    )

    parser.add_argument(
        "--build", action="store_true", help="Force rebuild of Docker images"
    )

    parser.add_argument(
        "--dev",
        action="store_true",
        help="Development mode - bind mount app source for hot reloading",
    )

    args = parser.parse_args()

    cli = PolyLlamaCLI()

    # Handle different commands
    if args.stop:
        return cli.stop()
    elif args.logs:
        return cli.logs()
    elif args.status:
        return cli.status()
    elif args.detect:
        return cli.detect()
    else:
        # Default action is to launch
        return cli.launch(debug=args.debug, build=args.build, dev_mode=args.dev)


if __name__ == "__main__":
    sys.exit(main())
