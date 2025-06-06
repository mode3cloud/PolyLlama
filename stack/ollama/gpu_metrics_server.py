#!/usr/bin/env python3
"""
GPU Metrics Server - Runs in each Ollama container to expose GPU metrics
"""
import json
import subprocess
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests for GPU metrics"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/metrics/gpu':
            try:
                # Get GPU metrics using nvidia-smi
                metrics = self.get_gpu_metrics()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(metrics).encode())
            except Exception as e:
                self.send_error(500, f"Error collecting metrics: {str(e)}")
        else:
            self.send_error(404, "Not found")
    
    def get_gpu_metrics(self):
        """Collect GPU metrics using nvidia-smi"""
        metrics = []
        
        # Get CUDA_VISIBLE_DEVICES to know which GPUs we have access to
        cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES', '')
        if not cuda_devices:
            return metrics
        
        # Parse GPU indices
        gpu_indices = [int(idx.strip()) for idx in cuda_devices.split(',') if idx.strip()]
        
        for gpu_idx in gpu_indices:
            try:
                # Run nvidia-smi for this specific GPU
                cmd = [
                    'nvidia-smi',
                    '--id=' + str(gpu_idx),
                    '--query-gpu=index,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw',
                    '--format=csv,noheader,nounits'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                output = result.stdout.strip()
                
                if output:
                    # Parse CSV output
                    parts = [p.strip() for p in output.split(',')]
                    if len(parts) >= 6:
                        metrics.append({
                            'index': int(parts[0]),
                            'memory_used': float(parts[1]),
                            'memory_total': float(parts[2]),
                            'gpu_utilization': float(parts[3]),
                            'temperature': float(parts[4]),
                            'power_draw': float(parts[5]) if parts[5] != '[N/A]' else None,
                            'timestamp': None  # Will be set by nginx
                        })
            except Exception as e:
                print(f"Error getting metrics for GPU {gpu_idx}: {e}")
        
        return metrics
    
    def log_message(self, format, *args):
        """Suppress request logging"""
        pass

def run_server(port=11435):
    """Run the metrics HTTP server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, MetricsHandler)
    print(f"GPU Metrics server listening on port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()