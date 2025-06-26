#!/usr/bin/env python3
"""Test script to verify sticky model routing for OpenAI-compatible endpoint"""

import requests
import json
import time

# Test parameters
BASE_URL = "http://localhost:11434"
MODEL_NAME = "llama3.2:latest"
NUM_REQUESTS = 5

def test_openai_endpoint():
    """Test the OpenAI-compatible endpoint for sticky routing"""
    print(f"\nTesting OpenAI-compatible endpoint with model: {MODEL_NAME}")
    print("=" * 60)
    
    instances = []
    
    for i in range(NUM_REQUESTS):
        print(f"\nRequest {i+1}:")
        
        # Make a request to the OpenAI-compatible endpoint
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
                "stream": False
            }
        )
        
        # Check which instance served the request
        served_by = response.headers.get("X-Served-By", "Unknown")
        instances.append(served_by)
        
        print(f"  Status: {response.status_code}")
        print(f"  Served by: {served_by}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Response: {data.get('choices', [{}])[0].get('message', {}).get('content', 'No content')[:50]}...")
        else:
            print(f"  Error: {response.text[:100]}...")
        
        # Small delay between requests
        time.sleep(0.5)
    
    # Check if all requests went to the same instance
    unique_instances = set(instances)
    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Total requests: {NUM_REQUESTS}")
    print(f"  Unique instances used: {len(unique_instances)}")
    print(f"  Instances: {unique_instances}")
    
    if len(unique_instances) == 1:
        print(f"  ✅ SUCCESS: All requests were routed to the same instance!")
    else:
        print(f"  ❌ FAILURE: Requests were routed to different instances!")
        print(f"  Instance distribution: {instances}")
    
    return len(unique_instances) == 1

def test_litellm_proxy():
    """Test through LiteLLM proxy to see if it properly routes"""
    print(f"\n\nTesting through LiteLLM proxy with model: ollama/{MODEL_NAME}")
    print("=" * 60)
    
    instances = []
    
    for i in range(NUM_REQUESTS):
        print(f"\nRequest {i+1}:")
        
        # Make a request through LiteLLM proxy
        response = requests.post(
            "http://localhost:11435/api/chat",
            headers={"Content-Type": "application/json"},
            json={
                "model": f"ollama/{MODEL_NAME}",
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
                "stream": False
            }
        )
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            # For streaming responses, we need to read the complete response
            content = ""
            for line in response.text.strip().split('\n'):
                if line.strip():
                    try:
                        if line.startswith('data: '):
                            chunk_data = json.loads(line[6:])
                            if chunk_data.get('type') == 'content':
                                content += chunk_data.get('content', '')
                    except:
                        pass
            print(f"  Response: {content[:50]}...")
            
            # Check router logs to see which instance was used
            # (We can't get X-Served-By through the proxy)
        else:
            print(f"  Error: {response.text[:100]}...")
        
        time.sleep(0.5)
    
    print(f"\n{'=' * 60}")
    print("Check router logs to verify if sticky routing worked through LiteLLM proxy")
    print("Run: docker logs router | grep 'Assigned model'")

if __name__ == "__main__":
    # Test OpenAI-compatible endpoint directly
    openai_success = test_openai_endpoint()
    
    # Test through LiteLLM proxy
    test_litellm_proxy()