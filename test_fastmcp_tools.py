#!/usr/bin/env python3
"""
Test FastMCP server with tool listing and calling
"""

import httpx
import json
import asyncio

async def test_fastmcp_with_tools():
    """Test FastMCP server with tools."""
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        print("=== Testing FastMCP with Tool Support ===\n")
        
        # Step 1: Initialize to establish session
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
        
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Error: {response.text}")
            return
        
        # Extract session ID if present  
        session_id = response.headers.get("mcp-session-id") or "test-session-123"
        print(f"   Session ID: {session_id}")
        
        # Parse SSE response
        lines = response.text.strip().split('\n')
        init_success = False
        for line in lines:
            if line.startswith('data: '):
                data = json.loads(line[6:])
                if data.get("result"):
                    print(f"   ✅ Initialize successful")
                    init_success = True
                    break
        
        if not init_success:
            print("   ❌ Initialize failed")
            return
        
        # Step 2: List tools
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
                "MCP-Session-ID": session_id
            }
        )
        
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Error: {response.text}")
            return
        
        # Parse tools response
        lines = response.text.strip().split('\n')
        tools = []
        for line in lines:
            if line.startswith('data: '):
                data = json.loads(line[6:])
                result = data.get("result", {})
                tools = result.get("tools", [])
                break
        
        if tools:
            print(f"   ✅ Found {len(tools)} tools")
            print(f"   First 5 tools: {[t['name'] for t in tools[:5]]}")
            
            # Step 3: Try to call a simple tool
            if tools:
                test_tool = tools[0]  # Try the first tool
                tool_name = test_tool["name"]
                
                print(f"\n3. Testing tool call: {tool_name}")
                response = await client.post(
                    "http://localhost:3001/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": {}
                        },
                        "id": 3
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "MCP-Session-ID": session_id
                    }
                )
                
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"   ✅ Tool call successful")
                    # Parse response
                    lines = response.text.strip().split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            data = json.loads(line[6:])
                            result = data.get("result", {})
                            content = result.get("content", [])
                            if content:
                                print(f"   Tool result: {content[0].get('text', '')[:100]}...")
                            break
                else:
                    print(f"   Tool call error: {response.text}")
        else:
            print("   ❌ No tools found")

if __name__ == "__main__":
    asyncio.run(test_fastmcp_with_tools())