#!/usr/bin/env python3
"""
Test script for LM Studio integration with PolyLlama.

This script tests:
1. Direct connection to LM Studio
2. Model discovery through LLM Proxy
3. Chat completion through unified API
"""

import os
import asyncio
import httpx
import json
from typing import Optional


async def test_direct_lmstudio_connection():
    """Test direct connection to LM Studio."""
    lmstudio_base = os.getenv("LMSTUDIO_API_BASE", "http://host.docker.internal:9090")

    print(f"\n=== Testing Direct LM Studio Connection ===")
    print(f"LM Studio Base URL: {lmstudio_base}")

    try:
        # Try to get models directly from LM Studio
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{lmstudio_base}/v1/models")

            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                print(f"✅ Connected to LM Studio successfully")
                print(f"   Found {len(models)} models:")
                for model in models[:5]:  # Show first 5 models
                    print(f"   - {model.get('id', 'unknown')}")
                return True
            else:
                print(f"❌ Failed to connect: HTTP {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("   Make sure LM Studio server is running on port 9090")
        return False


async def test_llm_proxy_models():
    """Test model discovery through LLM Proxy."""
    print(f"\n=== Testing LLM Proxy Model Discovery ===")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test connection to LLM Proxy
            response = await client.get("http://localhost:11435/api/models")

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])

                # Filter for LM Studio models
                lmstudio_models = [m for m in models if m.get("provider") == "lmstudio"]

                print(f"✅ LLM Proxy connected successfully")
                print(f"   Total models: {len(models)}")
                print(f"   LM Studio models: {len(lmstudio_models)}")

                if lmstudio_models:
                    print("   LM Studio models found:")
                    for model in lmstudio_models[:5]:
                        print(f"   - {model.get('id')} (vision: {model.get('supports_vision', False)}, tools: {model.get('supports_tools', False)})")
                else:
                    print("   ⚠️  No LM Studio models found in proxy")
                    print("      Make sure LMSTUDIO_API_BASE is set in .env")

                return len(lmstudio_models) > 0
            else:
                print(f"❌ Failed to connect to LLM Proxy: HTTP {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ LLM Proxy connection failed: {e}")
        print("   Make sure PolyLlama is running (./polyllama.sh)")
        return False


async def test_chat_completion(model: Optional[str] = None):
    """Test chat completion through unified API."""
    print(f"\n=== Testing Chat Completion ===")

    if not model:
        # Try to get first available LM Studio model
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("http://localhost:11435/api/models")
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    lmstudio_models = [m for m in models if m.get("provider") == "lmstudio"]
                    if lmstudio_models:
                        model = lmstudio_models[0]["id"]
                        print(f"   Using model: {model}")
        except:
            pass

    if not model:
        print("❌ No LM Studio model available for testing")
        return False

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test chat completion
            request_data = {
                "model": model,
                "messages": [
                    {"role": "user", "content": "Say 'Hello from LM Studio!' in exactly those words."}
                ],
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 50
            }

            print(f"   Sending test message to {model}...")
            response = await client.post(
                "http://localhost:11435/api/chat/completions",
                json=request_data,
                headers={"Accept": "application/json"}
            )

            if response.status_code == 200:
                # Handle streaming response by reading all chunks
                if response.headers.get("content-type") == "text/event-stream":
                    content = ""
                    for line in response.text.split("\n"):
                        if line.startswith("data: ") and line != "data: [DONE]":
                            try:
                                chunk = json.loads(line[6:])
                                if "choices" in chunk and chunk["choices"]:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content += delta.get("content", "")
                            except:
                                pass
                    print(f"✅ Chat completion successful")
                    print(f"   Response: {content[:100]}...")
                else:
                    # Non-streaming response
                    data = response.json()
                    print(f"✅ Chat completion successful")
                    if "choices" in data and data["choices"]:
                        content = data["choices"][0].get("message", {}).get("content", "")
                        print(f"   Response: {content[:100]}...")

                return True
            else:
                print(f"❌ Chat completion failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False

    except Exception as e:
        print(f"❌ Chat completion failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("LM Studio Integration Test for PolyLlama")
    print("=" * 60)

    # Check environment
    lmstudio_base = os.getenv("LMSTUDIO_API_BASE")
    if not lmstudio_base:
        print("\n⚠️  LMSTUDIO_API_BASE not set in environment")
        print("   Using default: host.docker.internal:9090")
        print("   To set: export LMSTUDIO_API_BASE=host.docker.internal:9090")

    # Run tests
    results = {
        "Direct Connection": await test_direct_lmstudio_connection(),
        "Model Discovery": await test_llm_proxy_models(),
        "Chat Completion": await test_chat_completion(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:.<30} {status}")

    all_passed = all(results.values())
    print("\n" + ("✅ All tests passed!" if all_passed else "❌ Some tests failed"))

    if not all_passed:
        print("\nTroubleshooting:")
        print("1. Make sure LM Studio is running and server is started")
        print("2. Check that LM Studio is on port 9090 (default)")
        print("3. Ensure PolyLlama is running: ./polyllama.sh")
        print("4. Set LMSTUDIO_API_BASE in .env file")
        print("5. Load at least one model in LM Studio")


if __name__ == "__main__":
    asyncio.run(main())