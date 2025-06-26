#!/usr/bin/env python3
"""Test to simulate UI flow through LiteLLM proxy to reproduce routing issue"""

import requests
import time
import subprocess
import json

# Configuration
MODEL = "gemma3:latest"
API_KEY = "sk-polyllama-test-key-123456789"

print(f"Testing UI flow routing for {MODEL}")
print("=" * 60)

# First unload the model if it exists
print("\n0. Ensuring clean state - unloading model if loaded...")
for i in [1, 2]:
    try:
        resp = requests.delete(
            f"http://localhost:11434/api/delete",
            headers={"api-key": API_KEY},
            json={"model": MODEL}
        )
        print(f"   Delete from instance {i}: {resp.status_code}")
    except:
        pass

time.sleep(3)

print("\n1. First request through LiteLLM proxy (simulating UI flow):")
# This simulates what the UI does: calls LiteLLM which then calls Ollama with OpenAI format
response1 = requests.post(
    "http://localhost:11435/api/chat/completions",  # LiteLLM proxy endpoint
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"  # API key for Ollama
    },
    json={
        "model": f"ollama/{MODEL}",  # LiteLLM format
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": False
    }
)
print(f"   Status: {response1.status_code}")
if response1.status_code != 200:
    print(f"   Error: {response1.text}")

# Wait for model to fully load
print("   Waiting for model to load...")
time.sleep(5)

# Check logs
print("\n   Checking router logs after first request:")
result = subprocess.run([
    "docker-compose", "-f", "builder/built/docker-compose.yml", 
    "exec", "router", "tail", "-50", "/var/log/nginx.out.log"
], capture_output=True, text=True)

for line in result.stdout.split('\n'):
    if (MODEL in line or "POST /v1" in line) and any(keyword in line for keyword in ["running on", "Assigned", "mapping", "Proxying", "Processing request"]):
        print(f"   LOG: {line.strip()}")

print("\n2. Second request through LiteLLM proxy - should use same instance:")
response2 = requests.post(
    "http://localhost:11435/api/chat/completions",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    },
    json={
        "model": f"ollama/{MODEL}",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False
    }
)
print(f"   Status: {response2.status_code}")
if response2.status_code != 200:
    print(f"   Error: {response2.text}")

time.sleep(3)

# Check where model is running
print("\n3. Checking where model is actually running:")
ps_response = requests.get(f"http://localhost:11434/api/ps", headers={"api-key": API_KEY})
if ps_response.status_code == 200:
    models = ps_response.json().get('models', [])
    for model in models:
        if model['name'] == MODEL:
            instances = model.get('instances', [])
            print(f"   Model {MODEL} is running on: {instances}")
            if len(instances) > 1:
                print("   ❌ ERROR: Model is running on multiple instances!")
            else:
                print("   ✅ OK: Model is only on one instance")

# Final log check
print("\n   Final router logs:")
result = subprocess.run([
    "docker-compose", "-f", "builder/built/docker-compose.yml", 
    "exec", "router", "tail", "-100", "/var/log/nginx.out.log"
], capture_output=True, text=True)

relevant_lines = []
for line in result.stdout.split('\n'):
    if (MODEL in line or "POST /v1" in line) and any(keyword in line for keyword in ["running on", "Assigned", "mapping", "Proxying", "Force refresh", "Processing request"]):
        relevant_lines.append(line.strip())

for line in relevant_lines[-20:]:
    print(f"   LOG: {line}")