#!/usr/bin/env python3
"""
Test FastMCP server HTTP transport
"""

import httpx
import json
import asyncio

async def test_fastmcp_http():
    """Test FastMCP server via HTTP transport."""
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        print("=== Testing FastMCP HTTP Transport ===\n")
        
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
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        )
        
        # Parse SSE response
        lines = response.text.strip().split('\n')
        for line in lines:
            if line.startswith('data: '):
                data = json.loads(line[6:])
                print(f"   Response: {json.dumps(data, indent=2)}")
                break
        
        print(f"   Status: {response.status_code}")
        
        # Create session for subsequent requests
        session_id = "test-session-123"
        
        # List tools
        print("\n2. Listing tools...")
        response = await client.post(
            "http://localhost:3001/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "X-Session-ID": session_id
            }
        )
        
        # Parse response
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            for line in lines:
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    tools = data.get("result", {}).get("tools", [])
                    print(f"   Found {len(tools)} tools")
                    if tools:
                        print(f"   First 5 tools: {[t['name'] for t in tools[:5]]}")
                    break
        else:
            print(f"   Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    asyncio.run(test_fastmcp_http())