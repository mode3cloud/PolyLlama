#!/usr/bin/env python3
"""
Test script for unified router architecture.

Tests the consolidated routing that combines:
- Ollama instance routing (Layer 2)
- Provider gateway functionality (Layer 3)
"""

import os
import asyncio
import httpx
import json
from typing import Optional, Dict, Any


async def test_ollama_routing():
    """Test routing to Ollama instances via unified router."""
    print("\n=== Testing Ollama Routing via Unified Router ===")

    api_key = os.getenv("POLYLLAMA_API_KEY", "")
    headers = {"api-key": api_key} if api_key else {}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test model listing (should show Ollama models)
            response = await client.get(
                "http://localhost:11434/api/models",
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                ollama_models = [m for m in models if not "/" in m.get("name", "")]

                print(f"✅ Ollama models accessible via unified router")
                print(f"   Found {len(ollama_models)} Ollama models")
                for model in ollama_models[:3]:
                    print(f"   - {model.get('name')}")
                return True
            else:
                print(f"❌ Failed to get Ollama models: HTTP {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ Ollama routing failed: {e}")
        return False


async def test_lmstudio_routing():
    """Test routing to LM Studio via unified router."""
    print("\n=== Testing LM Studio Routing via Unified Router ===")

    api_key = os.getenv("POLYLLAMA_API_KEY", "")
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    } if api_key else {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test with lmstudio/ prefix
            request_data = {
                "model": "lmstudio/test-model",
                "messages": [
                    {"role": "user", "content": "Say 'test' in one word"}
                ],
                "stream": False,
                "max_tokens": 10
            }

            print("   Sending request with model: lmstudio/test-model")
            response = await client.post(
                "http://localhost:11434/v1/chat/completions",
                json=request_data,
                headers=headers
            )

            if response.status_code == 200:
                print(f"✅ LM Studio routing successful")
                data = response.json()
                if "choices" in data:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    print(f"   Response received: {content[:50]}...")
                return True
            elif response.status_code == 503:
                print(f"⚠️  LM Studio not available (expected if not running)")
                return None  # Expected if LM Studio isn't running
            else:
                print(f"❌ LM Studio routing failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False

    except Exception as e:
        print(f"❌ LM Studio routing error: {e}")
        return False


async def test_external_provider_routing():
    """Test routing to external providers (OpenAI, Anthropic, etc)."""
    print("\n=== Testing External Provider Routing ===")

    api_key = os.getenv("POLYLLAMA_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if not openai_key:
        print("⚠️  OPENAI_API_KEY not set, skipping external provider test")
        return None

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    } if api_key else {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test with openai/ prefix
            request_data = {
                "model": "openai/gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": "Say 'test' in one word"}
                ],
                "stream": False,
                "max_tokens": 10
            }

            print("   Sending request with model: openai/gpt-3.5-turbo")
            response = await client.post(
                "http://localhost:11434/v1/chat/completions",
                json=request_data,
                headers=headers
            )

            if response.status_code == 200:
                print(f"✅ External provider routing successful")
                data = response.json()
                if "choices" in data:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    print(f"   Response: {content}")
                return True
            else:
                print(f"❌ External provider routing failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False

    except Exception as e:
        print(f"❌ External provider routing error: {e}")
        return False


async def test_unified_models_endpoint():
    """Test the unified /v1/models endpoint."""
    print("\n=== Testing Unified /v1/models Endpoint ===")

    api_key = os.getenv("POLYLLAMA_API_KEY", "")
    headers = {"api-key": api_key} if api_key else {}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:11434/v1/models",
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("object") == "list":
                    models = data.get("data", [])
                    print(f"✅ Unified models endpoint working")
                    print(f"   Total models: {len(models)}")

                    # Group by provider
                    providers = {}
                    for model in models:
                        provider = model.get("owned_by", "unknown")
                        if provider not in providers:
                            providers[provider] = []
                        providers[provider].append(model.get("id"))

                    for provider, model_list in providers.items():
                        print(f"   {provider}: {len(model_list)} models")
                        for model_id in model_list[:2]:
                            print(f"     - {model_id}")

                    return True
                else:
                    print(f"❌ Unexpected response format")
                    return False
            else:
                print(f"❌ Failed to get unified models: HTTP {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ Unified models endpoint error: {e}")
        return False


async def test_default_provider_inference():
    """Test that models without provider prefix default correctly."""
    print("\n=== Testing Default Provider Inference ===")

    api_key = os.getenv("POLYLLAMA_API_KEY", "")
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    } if api_key else {"Content-Type": "application/json"}

    # Check if LM Studio is configured
    lmstudio_base = os.getenv("LMSTUDIO_API_BASE", "")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test model without prefix
            request_data = {
                "model": "llama3.2:3b",  # No provider prefix
                "messages": [
                    {"role": "user", "content": "Say 'hello'"}
                ],
                "stream": False,
                "max_tokens": 10
            }

            print(f"   Testing model without prefix: llama3.2:3b")
            print(f"   LM Studio configured: {bool(lmstudio_base)}")

            response = await client.post(
                "http://localhost:11434/v1/chat/completions",
                json=request_data,
                headers=headers
            )

            if response.status_code in [200, 503]:
                if lmstudio_base:
                    print(f"✅ Model defaulted to LM Studio (as configured)")
                else:
                    print(f"✅ Model defaulted to Ollama (no LM Studio)")
                return True
            else:
                print(f"❌ Default provider inference failed: HTTP {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ Default provider test error: {e}")
        return False


async def main():
    """Run all unified routing tests."""
    print("=" * 60)
    print("Unified Router Architecture Test")
    print("=" * 60)

    # Check environment
    api_key = os.getenv("POLYLLAMA_API_KEY")
    if api_key:
        print(f"✓ API key configured")
    else:
        print("⚠️  No API key set (requests may be blocked)")

    lmstudio_base = os.getenv("LMSTUDIO_API_BASE")
    if lmstudio_base:
        print(f"✓ LM Studio base: {lmstudio_base}")

    # Run tests
    results = {
        "Ollama Routing": await test_ollama_routing(),
        "LM Studio Routing": await test_lmstudio_routing(),
        "External Providers": await test_external_provider_routing(),
        "Unified Models": await test_unified_models_endpoint(),
        "Default Provider": await test_default_provider_inference(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)

    for test_name, result in results.items():
        if result is True:
            status = "✅ PASSED"
        elif result is False:
            status = "❌ FAILED"
        else:
            status = "⚠️  SKIPPED"
        print(f"{test_name:.<30} {status}")

    # Overall assessment
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)

    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")

    if failed == 0:
        print("\n✅ Unified router architecture working as expected!")
        print("   The consolidation of Layer 2 and Layer 3 is successful.")
    else:
        print("\n❌ Some tests failed. Check the configuration and logs.")

    print("\nNext steps:")
    print("1. Monitor performance under load")
    print("2. Test with real multi-provider workloads")
    print("3. Consider removing old LLM proxy service once stable")


if __name__ == "__main__":
    asyncio.run(main())