#!/usr/bin/env python3
"""
Dynamic Docker Compose Generator for Ollama Stack
Generates compose file from template based on detected GPU configuration
"""

import json
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

def render_template_with_jinja2(template_path, context):
    """
    Render template using Jinja2 template engine
    """
    try:
        # Set up Jinja2 environment
        template_dir = template_path.parent
        env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Load and render template
        template = env.get_template(template_path.name)
        return template.render(context)
        
    except Exception as e:
        print(f"Error rendering template {template_path}: {e}")
        sys.exit(1)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 generate_compose.py <gpu_config_json>")
        sys.exit(1)
    
    # Parse GPU configuration from command line argument
    try:
        gpu_config = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"Error parsing GPU configuration JSON: {e}")
        sys.exit(1)
    
    # Define template paths
    compose_template_path = Path(__file__).parent / "docker-compose.yml.j2"
    nginx_template_path = Path(__file__).parent.parent / "stack/router/nginx.conf.j2"
    
    # Check templates exist
    if not compose_template_path.exists():
        print(f"Error: Docker Compose template not found at {compose_template_path}")
        sys.exit(1)
    
    if not nginx_template_path.exists():
        print(f"Error: Nginx template not found at {nginx_template_path}")
        sys.exit(1)
    
    # Prepare context for template
    ollama_instances = []
    
    if not gpu_config.get('gpu_groups'):
        # CPU-only configuration
        ollama_instances.append({
            'number': 1,
            'gpu_indices': None,
            'memory_limit': 16,
            'gpu_name': 'CPU-only',
            'gpu_count': 0
        })
    else:
        # GPU-based configurations
        for i, group in enumerate(gpu_config['gpu_groups']):
            instance_num = i + 1
            gpu_count = len(group['indices'])
            memory_limit = max(16, gpu_count * 32)
            
            ollama_instances.append({
                'number': instance_num,
                'gpu_indices': ','.join(map(str, group['indices'])),
                'memory_limit': memory_limit,
                'gpu_name': group['name'],
                'gpu_count': gpu_count
            })
    
    context = {
        'ollama_instances': ollama_instances,
        'instance_count': len(ollama_instances)
    }
    
    # Render templates using Jinja2
    compose_result = render_template_with_jinja2(compose_template_path, context)
    nginx_result = render_template_with_jinja2(nginx_template_path, context)
    
    # Create runtime directory if it doesn't exist
    runtime_dir = Path(__file__).parent.parent / "runtime"
    runtime_dir.mkdir(exist_ok=True)
    
    # Write results to runtime directory with normal names
    compose_output_path = runtime_dir / "docker-compose.yml"
    nginx_output_path = runtime_dir / "nginx.conf"
    
    try:
        with open(compose_output_path, 'w') as f:
            f.write(compose_result)
        
        with open(nginx_output_path, 'w') as f:
            f.write(nginx_result)
            
        print(f"Generated {compose_output_path} and {nginx_output_path} with {len(ollama_instances)} instance(s)")
        
    except IOError as e:
        print(f"Error writing output files: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()