#!/usr/bin/env python3
"""Test to trace /v1/chat/completions routing"""

import requests
import time
import subprocess

MODEL = "gemma3:latest"
API_KEY = "sk-polyllama-test-key-123456789"

print(f"Testing /v1/chat/completions routing for {MODEL}")
print("=" * 60)

# First unload the model
print("\n0. Ensuring clean state...")
for i in [1, 2, 3]:
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

print("\n1. First request directly to /v1/chat/completions:")
response1 = requests.post(
    "http://localhost:11434/v1/chat/completions",
    headers={
        "Content-Type": "application/json",
        "api-key": API_KEY
    },
    json={
        "model": MODEL,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": False
    }
)
print(f"   Status: {response1.status_code}")

# Check immediate logs
print("\n   Checking logs immediately after first request:")
result = subprocess.run([
    "docker-compose", "-f", "builder/built/docker-compose.yml", 
    "exec", "router", "tail", "-50", "/var/log/nginx.out.log"
], capture_output=True, text=True)

for line in result.stdout.split('\n'):
    if any(keyword in line for keyword in [
        "Processing request: Method=POST, URI=/v1/chat/completions",
        "Extracted model name",
        "is already running on",
        "Assigned model",
        "Force refresh",
        "Model " + MODEL
    ]):
        print(f"   LOG: {line.strip()}")

time.sleep(5)

print("\n2. Second request to /v1/chat/completions:")
response2 = requests.post(
    "http://localhost:11434/v1/chat/completions",
    headers={
        "Content-Type": "application/json",
        "api-key": API_KEY
    },
    json={
        "model": MODEL,
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False
    }
)
print(f"   Status: {response2.status_code}")

# Check logs again
print("\n   Checking logs after second request:")
result = subprocess.run([
    "docker-compose", "-f", "builder/built/docker-compose.yml", 
    "exec", "router", "tail", "-100", "/var/log/nginx.out.log"
], capture_output=True, text=True)

relevant_lines = []
for line in result.stdout.split('\n'):
    if any(keyword in line for keyword in [
        "Processing request: Method=POST, URI=/v1/chat/completions",
        "Extracted model name",
        "is already running on",
        "Assigned model",
        "Force refresh",
        "not found in cache",
        "Model " + MODEL
    ]):
        relevant_lines.append(line.strip())

for line in relevant_lines[-20:]:
    print(f"   LOG: {line}")

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