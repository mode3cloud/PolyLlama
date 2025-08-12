#!/usr/bin/env python3
"""
Complete test of MCP SSE transport with initialize and tools/list.
"""

import asyncio
import json
import httpx

async def test_mcp_sse():
    """Test MCP protocol over SSE transport."""
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Connect to SSE endpoint
        print("1. Connecting to SSE endpoint...")
        
        async with client.stream("GET", "http://localhost:3001/sse") as response:
            print(f"   Connected! Status: {response.status_code}")
            
            session_id = response.headers.get("x-session-id")
            print(f"   Session ID: {session_id}\n")
            
            # Create a task to read SSE events
            async def read_events():
                results = []
                try:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            results.append(data)
                            print(f"   <- Received: {json.dumps(data, indent=2)}")
                except asyncio.TimeoutError:
                    pass
                return results
            
            # Start reading events in background
            read_task = asyncio.create_task(read_events())
            
            # Wait for connection to establish
            await asyncio.sleep(0.5)
            
            # Send initialize message
            print("2. Sending initialize message...")
            init_message = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                },
                "id": 1
            }
            
            post_response = await client.post(
                f"http://localhost:3001/messages/{session_id}",
                json=init_message
            )
            print(f"   -> Sent initialize (status: {post_response.status_code})\n")
            
            # Wait for response
            await asyncio.sleep(1)
            
            # Send tools/list message
            print("3. Sending tools/list message...")
            tools_message = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            }
            
            post_response = await client.post(
                f"http://localhost:3001/messages/{session_id}",
                json=tools_message
            )
            print(f"   -> Sent tools/list (status: {post_response.status_code})\n")
            
            # Wait for response
            await asyncio.sleep(2)
            
            # Cancel read task
            read_task.cancel()
            try:
                results = await read_task
            except asyncio.CancelledError:
                results = []
            
            print("\n4. Summary:")
            print(f"   Total events received: {len(results)}")
            
            # Check for tools
            for result in results:
                if "result" in result and "tools" in result.get("result", {}):
                    tools = result["result"]["tools"]
                    print(f"   Tools available: {len(tools)}")
                    if tools:
                        print(f"   First 3 tools: {[t['name'] for t in tools[:3]]}")
            
            print("\n✅ SSE transport test complete!")

if __name__ == "__main__":
    asyncio.run(test_mcp_sse())