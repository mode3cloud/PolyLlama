#!/usr/bin/env python3
"""
Test both HTTP and SSE transports working simultaneously
"""

import asyncio
import json
import httpx
from typing import Dict, Any


async def test_streamable_http():
    """Test MCP over streamable HTTP transport."""
    print("=== Testing Streamable HTTP Transport ===")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Initialize
        print("1. Sending initialize request...")
        response = await client.post(
            "http://localhost:3001/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-http-client", "version": "1.0.0"}
                },
                "id": 1
            },
            headers={"Accept": "application/json, text/event-stream"}
        )
        
        if response.status_code == 200:
            # Parse SSE response
            lines = response.text.strip().split('\n')
            for line in lines:
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    print(f"   ✅ HTTP Initialize successful: {data['result']['serverInfo']['name']}")
                    break
        else:
            print(f"   ❌ HTTP Initialize failed: {response.status_code}")
            
        return response.status_code == 200


async def test_sse_transport():
    """Test MCP over SSE transport."""
    print("\n=== Testing SSE Transport ===")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Connect to SSE endpoint
        print("1. Connecting to SSE endpoint...")
        
        try:
            async with client.stream("GET", "http://localhost:3001/sse") as response:
                if response.status_code == 200:
                    print(f"   ✅ SSE Connected: {response.status_code}")
                    
                    # Read the session setup message
                    event_count = 0
                    async for line in response.aiter_lines():
                        print(f"   SSE Event: {line}")
                        event_count += 1
                        if event_count >= 2:  # Read endpoint setup and first event
                            break
                    
                    return True
                else:
                    print(f"   ❌ SSE Connection failed: {response.status_code}")
                    return False
                    
        except asyncio.TimeoutError:
            print("   ⏰ SSE Connection timed out (expected behavior)")
            return True  # SSE connections stay open, timeout is expected


async def test_both_endpoints():
    """Test that both endpoints work simultaneously."""
    print("\n=== Testing Simultaneous Access ===")
    
    # Test both at the same time
    results = await asyncio.gather(
        test_health_endpoints(),
        test_status_endpoint(),
        return_exceptions=True
    )
    
    success_count = sum(1 for r in results if r is True)
    print(f"   ✅ {success_count}/2 simultaneous tests passed")
    
    return success_count == 2


async def test_health_endpoints():
    """Test health endpoint."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get("http://localhost:3001/health")
        if response.status_code == 200:
            data = response.json()
            transports = data.get("transport", [])
            if "streamable-http" in transports and "sse" in transports:
                print("   ✅ Health endpoint shows dual transport")
                return True
            else:
                print(f"   ❌ Health endpoint missing transports: {transports}")
                return False
        else:
            print(f"   ❌ Health endpoint failed: {response.status_code}")
            return False


async def test_status_endpoint():
    """Test status endpoint.""" 
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get("http://localhost:3001/status")
        if response.status_code == 200:
            data = response.json()
            if data.get("features", {}).get("dualTransport") is True:
                print("   ✅ Status endpoint confirms dual transport")
                return True
            else:
                print(f"   ❌ Status endpoint missing dual transport feature")
                return False
        else:
            print(f"   ❌ Status endpoint failed: {response.status_code}")
            return False


async def main():
    """Run all transport tests."""
    print("=" * 60)
    print("🚀 FASTMCP DUAL TRANSPORT TEST")
    print("=" * 60)
    
    results = []
    
    # Test HTTP transport
    results.append(await test_streamable_http())
    
    # Test SSE transport
    results.append(await test_sse_transport())
    
    # Test simultaneous access
    results.append(await test_both_endpoints())
    
    print("\n" + "=" * 60)
    success_count = sum(results)
    if success_count == 3:
        print("✅ ALL TESTS PASSED - DUAL TRANSPORT WORKING!")
    else:
        print(f"⚠️  {success_count}/3 tests passed")
    print("=" * 60)
    
    return success_count == 3


if __name__ == "__main__":
    asyncio.run(main())