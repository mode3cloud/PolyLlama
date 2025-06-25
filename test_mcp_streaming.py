#!/usr/bin/env python3
"""
Test script to verify MCP tool streaming events are working correctly.

This script simulates a chat request with MCP tools enabled and prints
the streaming events to verify they're being sent correctly.
"""
import asyncio
import json
import aiohttp
import sys

# Configuration
API_BASE_URL = "http://localhost:11435"  # LLM Proxy direct port
API_KEY = "test-key"  # Replace with actual API key if needed
MODEL = "ollama/llama3.2:3b"  # Use a model that supports tools

async def test_mcp_streaming():
    """Test MCP tool streaming by making a chat request."""
    
    # Test message that should trigger tool usage
    messages = [
        {
            "role": "user",
            "content": "What's the weather like in San Francisco? Please use any available weather tools."
        }
    ]
    
    # Chat completion request payload
    payload = {
        "messages": messages,
        "model": MODEL,
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    print(f"Making request to: {API_BASE_URL}/api/chat/completions")
    print(f"Model: {MODEL}")
    print(f"Message: {messages[0]['content']}")
    print("-" * 50)
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{API_BASE_URL}/api/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status != 200:
                    print(f"Error: HTTP {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return
                
                # Process SSE stream
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        data = line[6:]
                        if data:
                            try:
                                event = json.loads(data)
                                event_type = event.get('type', 'unknown')
                                
                                # Format output based on event type
                                if event_type == 'connected':
                                    print("✅ Connected to stream")
                                elif event_type == 'content':
                                    print(f"📝 Content: {event.get('content', '')}", end='', flush=True)
                                elif event_type == 'tool_call_streaming':
                                    tool_call = event.get('tool_call', {})
                                    print(f"\n🔧 Tool streaming: {tool_call.get('name')} (status: {tool_call.get('status')})")
                                elif event_type == 'tool_call':
                                    tool_call = event.get('tool_call', {})
                                    print(f"\n🔨 Tool call: {tool_call.get('name')}")
                                    print(f"   Arguments: {json.dumps(tool_call.get('arguments', {}), indent=2)}")
                                elif event_type == 'tool_result':
                                    print(f"\n✨ Tool result from {event.get('name')}:")
                                    print(f"   {event.get('result', 'No result')}")
                                elif event_type == 'tool_error':
                                    print(f"\n❌ Tool error from {event.get('name')}: {event.get('error')}")
                                elif event_type == 'error':
                                    print(f"\n❌ Error: {event.get('error')}")
                                elif event_type == 'done':
                                    print("\n✅ Stream completed")
                                else:
                                    print(f"\n❓ Unknown event type: {event_type}")
                                    print(f"   Data: {json.dumps(event, indent=2)}")
                            except json.JSONDecodeError as e:
                                print(f"\n⚠️  Failed to parse JSON: {e}")
                                print(f"   Raw data: {data}")
                
        except aiohttp.ClientError as e:
            print(f"Connection error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """Main entry point."""
    print("MCP Tool Streaming Test")
    print("=" * 50)
    
    # Check if MCP tools are available
    print("\nChecking MCP tools availability...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{API_BASE_URL}/api/mcp/tools",
                headers={"Authorization": f"Bearer {API_KEY}"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    tools = data.get('tools', [])
                    print(f"✅ Found {len(tools)} MCP tools available")
                    if tools:
                        print("Available tools:")
                        for tool in tools[:5]:  # Show first 5 tools
                            print(f"  - {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')[:60]}...")
                        if len(tools) > 5:
                            print(f"  ... and {len(tools) - 5} more")
                else:
                    print(f"⚠️  Could not fetch tools: HTTP {response.status}")
        except Exception as e:
            print(f"⚠️  Error checking tools: {e}")
    
    print("\n" + "-" * 50)
    print("Testing chat with tool execution...\n")
    
    await test_mcp_streaming()

if __name__ == "__main__":
    asyncio.run(main())