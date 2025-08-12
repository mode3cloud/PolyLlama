#!/usr/bin/env python3
"""
Debug FastMCP session management
"""

import httpx
import json
import asyncio

async def debug_session():
    """Debug how FastMCP manages sessions."""
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        print("=== Debugging FastMCP Session Management ===\n")
        
        # Initialize and capture all headers
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
        print(f"   All Headers: {dict(response.headers)}")
        
        # Check for various session header formats
        session_headers = [
            "x-session-id",
            "session-id", 
            "mcp-session-id",
            "sessionid",
            "X-Session-ID",
            "MCP-Session-ID"
        ]
        
        session_id = None
        for header in session_headers:
            value = response.headers.get(header)
            if value:
                session_id = value
                print(f"   Found session in header '{header}': {value}")
                break
        
        if not session_id:
            print("   No session ID found in headers")
            
        # Check response body for session info
        print(f"   Response body: {response.text[:200]}...")
        
        # Try different session header formats in the next request
        for header_name in ["X-Session-ID", "x-session-id", "Session-ID", "MCP-Session-ID"]:
            print(f"\n2. Testing tools/list with header '{header_name}'...")
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
            
            if session_id:
                headers[header_name] = session_id
            else:
                headers[header_name] = "test-session"
                
            response = await client.post(
                "http://localhost:3001/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": 2
                },
                headers=headers
            )
            
            print(f"   Status: {response.status_code}")
            if response.status_code != 400:
                print(f"   ✅ Success with header '{header_name}'!")
                print(f"   Response: {response.text[:200]}...")
                break
            else:
                print(f"   ❌ Failed: {response.text}")

if __name__ == "__main__":
    asyncio.run(debug_session())