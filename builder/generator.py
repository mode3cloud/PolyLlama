"""
Docker Compose file generator for PolyLlama
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader


class ComposeGenerator:
    """Generates Docker Compose and Nginx configurations"""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.templates_dir = root_dir / "builder"
        self.stack_dir = root_dir / "stack"
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(self, config: Dict, output_dir: Path, dev_mode: bool = False):
        """
        Generate Docker Compose and Nginx configurations

        Args:
            config: Configuration dict with 'gpu_groups' key
            output_dir: Directory to write generated files
            dev_mode: Whether to generate configs for development mode
        """
        # Create output directory
        output_dir.mkdir(exist_ok=True)

        # Prepare template context
        ollama_instances = self._prepare_ollama_instances(config["gpu_groups"])
        instance_count = len(ollama_instances)

        context = {
            "ollama_instances": ollama_instances,
            "instance_count": instance_count,
            "dev_mode": dev_mode,
        }

        # Generate docker-compose.yml
        self._generate_compose_file(context, output_dir)

        # Generate nginx.conf
        self._generate_nginx_conf(context, output_dir)

        print(f"  Generated {len(ollama_instances)} instance(s) in {output_dir}")

    def _prepare_ollama_instances(self, gpu_groups: List[Dict]) -> List[Dict]:
        """
        Prepare Ollama instance configurations

        Args:
            gpu_groups: List of GPU groups from detector

        Returns:
            List of instance configurations for template
        """
        if not gpu_groups:
            # CPU-only configuration
            return [{
                "number": 1,
                "gpu_indices": None,
                "memory_limit": 16,
                "gpu_name": "CPU-only",
                "gpu_count": 0,
            }]

        instances = []
        for i, group in enumerate(gpu_groups, 1):
            # Calculate memory limit based on GPU count
            gpu_count = len(group["indices"])
            memory_limit = max(16, gpu_count * 32)  # 32GB per GPU as default

            instances.append({
                "number": i,
                "gpu_indices": ",".join(map(str, group["indices"])),
                "memory_limit": memory_limit,
                "gpu_name": group["name"],
                "gpu_count": gpu_count,
            })

        return instances

    def _generate_compose_file(self, context: Dict, output_dir: Path):
        """Generate docker-compose.yml from template"""
        template = self.env.get_template("docker-compose.yml.j2")
        content = template.render(**context)

        output_file = output_dir / "docker-compose.yml"
        output_file.write_text(content)

    def _generate_nginx_conf(self, context: Dict, output_dir: Path):
        """Generate nginx.conf from template"""
        # Load nginx template from builder directory (same as docker-compose template)
        template = self.env.get_template("nginx.conf.j2")
        content = template.render(**context)

        # Write to output directory directly (not in router subdirectory)
        output_file = output_dir / "nginx.conf"
        output_file.write_text(content)


# Keep the old main function for backward compatibility
def main():
    """Main function for standalone execution (backward compatibility)"""
    if len(sys.argv) != 2:
        print("Usage: python3 generator.py <gpu_config_json>")
        sys.exit(1)

    # Parse GPU configuration from command line argument
    try:
        gpu_config = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"Error parsing GPU configuration JSON: {e}")
        sys.exit(1)

    # Use the generator
    root_dir = Path(__file__).parent.parent
    generator = ComposeGenerator(root_dir)
    built_dir = Path(__file__).parent / "built"
    
    generator.generate(gpu_config, built_dir)


if __name__ == "__main__":
    import sys
    main()
