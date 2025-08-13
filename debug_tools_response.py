#!/usr/bin/env python3
"""
Debug the tools/list response content
"""

import httpx
import json
import asyncio

async def debug_tools_response():
    """Debug what's actually in the tools/list response."""
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        print("=== Debugging Tools/List Response ===\n")
        
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
                    "clientInfo": {"name": "debug-client", "version": "1.0.0"}
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
        
        # Extract session ID
        session_id = response.headers.get("mcp-session-id") or "debug-session-456"
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
        
        # Step 1.5: Send initialized notification (required by MCP protocol)
        print("\n1.5. Sending initialized notification...")
        init_notification = await client.post(
            "http://localhost:3001/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "MCP-Session-ID": session_id
            }
        )
        print(f"   Initialized notification status: {init_notification.status_code}")
        
        # Step 2: List tools with detailed debugging
        print("\n2. Listing tools with full response debugging...")
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
        print(f"   Response headers: {dict(response.headers)}")
        print(f"   Raw response text:\n{response.text}")
        
        if response.status_code != 200:
            print(f"   Error in response")
            return
        
        # Parse and analyze the response
        print("\n3. Parsing SSE response...")
        lines = response.text.strip().split('\n')
        event_count = 0
        
        for i, line in enumerate(lines):
            print(f"   Line {i}: {line}")
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    print(f"   Parsed data: {json.dumps(data, indent=2)}")
                    
                    result = data.get("result", {})
                    tools = result.get("tools", [])
                    print(f"   Tools count: {len(tools)}")
                    
                    if tools:
                        print("   First few tools:")
                        for j, tool in enumerate(tools[:3]):
                            print(f"     Tool {j}: {tool.get('name', 'unnamed')}")
                    
                    event_count += 1
                except json.JSONDecodeError as e:
                    print(f"   JSON decode error: {e}")
        
        print(f"\n4. Summary: Found {event_count} events")

if __name__ == "__main__":
    asyncio.run(debug_tools_response())