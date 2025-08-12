#!/usr/bin/env python3
"""
Test MCP server dual transport (HTTP + SSE) functionality.
"""

import asyncio
import json
import httpx
from typing import Dict, Any


async def test_streamable_http():
    """Test MCP over streamable HTTP transport."""
    print("\n=== Testing Streamable HTTP Transport ===\n")
    
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
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                },
                "id": 1
            },
            headers={"Accept": "application/json"}
        )
        print(f"   Response: {response.json()}")
        
        # List tools
        print("\n2. Listing tools...")
        response = await client.post(
            "http://localhost:3001/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2},
            headers={"Accept": "application/json"}
        )
        result = response.json()
        tools = result.get("result", {}).get("tools", [])
        print(f"   Found {len(tools)} tools")
        if tools:
            print(f"   First 3 tools: {[t['name'] for t in tools[:3]]}")


async def test_sse_transport():
    """Test MCP over SSE transport."""
    print("\n=== Testing SSE Transport ===\n")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Connect to SSE endpoint
        print("1. Connecting to SSE endpoint...")
        
        async with client.stream("GET", "http://localhost:3001/sse") as response:
            print(f"   Connected! Status: {response.status_code}")
            
            session_id = response.headers.get("x-session-id")
            print(f"   Session ID: {session_id}")
            
            # Create line iterator once
            line_iterator = response.aiter_lines()
            
            # Read initial ready signal
            initial_event = None
            async for line in line_iterator:
                if line.startswith("data: "):
                    initial_event = json.loads(line[6:])
                    print(f"   Ready signal: {json.dumps(initial_event, indent=2)}")
                    break
            
            # Verify it's the connection ready signal
            if initial_event and initial_event.get("method") == "connection/ready":
                print("   ✓ Received proper connection ready signal!")
                
                # Extract session ID from ready signal
                ready_session_id = initial_event.get("params", {}).get("sessionId")
                if ready_session_id:
                    print(f"   ✓ Session ID in ready signal: {ready_session_id}")
                
                # Now send initialize via POST
                print("\n2. Sending initialize message...")
                post_response = await client.post(
                    f"http://localhost:3001/messages/{session_id}",
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {},
                            "clientInfo": {"name": "test-sse-client", "version": "1.0.0"}
                        },
                        "id": 1
                    }
                )
                print(f"   Message sent: {post_response.status_code}")
                
                # Read response from SSE stream
                async def read_next_event():
                    async for line in line_iterator:
                        if line.startswith("data: "):
                            return json.loads(line[6:])
                    return None
                
                # Read initialize response
                init_response = await asyncio.wait_for(read_next_event(), timeout=2.0)
                if init_response:
                    print(f"   Initialize response: {json.dumps(init_response, indent=2)}")
                
                # Send tools/list
                print("\n3. Sending tools/list message...")
                post_response = await client.post(
                    f"http://localhost:3001/messages/{session_id}",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/list",
                        "params": {},
                        "id": 2
                    }
                )
                print(f"   Message sent: {post_response.status_code}")
                
                # Read tools response
                tools_response = await asyncio.wait_for(read_next_event(), timeout=2.0)
                if tools_response:
                    tools = tools_response.get("result", {}).get("tools", [])
                    print(f"   Found {len(tools)} tools via SSE")
                    if tools:
                        print(f"   First 3 tools: {[t['name'] for t in tools[:3]]}")
            else:
                print("   ✗ Did not receive expected connection ready signal")


async def main():
    """Run all transport tests."""
    print("=" * 60)
    print("MCP DUAL TRANSPORT TEST")
    print("=" * 60)
    
    # Test streamable HTTP
    await test_streamable_http()
    
    # Test SSE
    await test_sse_transport()
    
    print("\n" + "=" * 60)
    print("✅ DUAL TRANSPORT TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())