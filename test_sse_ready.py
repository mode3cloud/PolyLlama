#!/usr/bin/env python3
"""
Test SSE endpoint readiness signal.
"""

import httpx
import json
import asyncio

async def test_sse_ready():
    """Test SSE endpoint for readiness signal."""
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        print("Connecting to SSE endpoint...")
        
        async with client.stream("GET", "http://localhost:3001/sse") as response:
            print(f"Connected! Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            
            # Read first few events
            event_count = 0
            async for line in response.aiter_lines():
                print(f"Line: {repr(line)}")
                
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        print(f"Parsed data: {json.dumps(data, indent=2)}")
                    except json.JSONDecodeError:
                        print(f"Could not parse: {line[6:]}")
                
                event_count += 1
                if event_count > 5:
                    break
            
            print("\nSSE endpoint test complete!")

if __name__ == "__main__":
    asyncio.run(test_sse_ready())