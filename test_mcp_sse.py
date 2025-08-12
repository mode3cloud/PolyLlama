#!/usr/bin/env python3
"""
Test MCP SSE connection to understand what clients expect.
"""

import asyncio
import json
import httpx
from typing import AsyncGenerator

async def test_sse_connection():
    """Test connecting to the MCP server via SSE."""
    
    async with httpx.AsyncClient() as client:
        # Connect to SSE endpoint
        print("Connecting to SSE endpoint...")
        
        async with client.stream("GET", "http://localhost:3001/sse") as response:
            print(f"Connected! Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            
            session_id = response.headers.get("x-session-id")
            print(f"Session ID: {session_id}")
            
            # Read some initial events
            lines_read = 0
            async for line in response.aiter_lines():
                print(f"SSE: {line}")
                lines_read += 1
                
                # After getting session info, try to send an initialize message
                if "messages/" in line and session_id:
                    print(f"\nFound message endpoint in: {line}")
                    print("Sending initialize message...")
                    
                    # Send initialize message via POST
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
                    print(f"POST response: {post_response.status_code}")
                    print(f"POST body: {post_response.text}")
                
                if lines_read > 10:
                    break
            
            print("\nTest complete!")

if __name__ == "__main__":
    asyncio.run(test_sse_connection())