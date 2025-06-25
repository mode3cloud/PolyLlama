#!/usr/bin/env python3
"""
Test script to verify MCP tool error handling.

This script tests that MCP validation errors and other failures are properly
passed back to the LLM instead of throwing HTTP 500 errors.
"""
import asyncio
import json
import aiohttp
import sys

# Configuration
API_BASE_URL = "http://localhost:11435"  # LLM Proxy direct port
API_KEY = "test-key"  # Replace with actual API key if needed
MODEL = "ollama/llama3.2:3b"  # Use a model that supports tools

async def test_mcp_error_handling():
    """Test MCP error handling with various failure scenarios."""
    
    # Test cases that should trigger different types of errors
    test_cases = [
        {
            "name": "Invalid GitHub user search",
            "message": "Search for issues created by user 'nonexistentuser12345' in the GitHub repository",
            "expected_error": "users do not exist"
        },
        {
            "name": "Invalid tool arguments",
            "message": "Use the search_issues tool with invalid parameters",
            "expected_error": "Validation"
        },
        {
            "name": "Non-existent tool",
            "message": "Use the 'make_coffee' tool to brew some coffee",
            "expected_error": "tool"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n{'='*60}")
        print(f"Test: {test_case['name']}")
        print(f"Message: {test_case['message']}")
        print(f"Expected error keyword: {test_case['expected_error']}")
        print("-" * 60)
        
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant with access to various tools. When a tool fails, explain the error and suggest alternatives."
            },
            {
                "role": "user",
                "content": test_case['message']
            }
        ]
        
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
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{API_BASE_URL}/api/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    print(f"Response status: {response.status}")
                    
                    if response.status != 200:
                        print(f"❌ ERROR: HTTP {response.status}")
                        text = await response.text()
                        print(f"Response: {text}")
                        continue
                    
                    # Process SSE stream
                    tool_error_found = False
                    error_content = []
                    
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data = line[6:]
                            if data:
                                try:
                                    event = json.loads(data)
                                    event_type = event.get('type', 'unknown')
                                    
                                    if event_type == 'tool_call':
                                        tool_call = event.get('tool_call', {})
                                        print(f"🔨 Tool call: {tool_call.get('name')}")
                                        
                                    elif event_type == 'tool_result':
                                        result = event.get('result', '')
                                        if 'failed' in result.lower() or 'error' in result.lower():
                                            tool_error_found = True
                                            error_content.append(result)
                                            print(f"⚠️  Tool error detected: {result[:100]}...")
                                        else:
                                            print(f"✅ Tool result: {result[:100]}...")
                                        
                                    elif event_type == 'tool_error':
                                        tool_error_found = True
                                        error = event.get('error', '')
                                        error_content.append(error)
                                        print(f"❌ Tool error event: {error}")
                                        
                                    elif event_type == 'content':
                                        # Don't print all content, just track it
                                        pass
                                        
                                    elif event_type == 'error':
                                        print(f"❌ Stream error: {event.get('error')}")
                                        
                                except json.JSONDecodeError:
                                    pass
                    
                    # Check results
                    if tool_error_found:
                        print(f"\n✅ SUCCESS: Tool error was properly handled")
                        print(f"Error content included expected keyword: {any(test_case['expected_error'].lower() in err.lower() for err in error_content)}")
                    else:
                        print(f"\n⚠️  No tool error detected (might be okay if tool wasn't called)")
                        
            except Exception as e:
                print(f"❌ Connection error: {e}")
                import traceback
                traceback.print_exc()

async def main():
    """Main entry point."""
    print("MCP Tool Error Handling Test")
    print("=" * 60)
    
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
                    
                    # Look for GitHub tools
                    github_tools = [t for t in tools if 'github' in t.get('name', '').lower()]
                    if github_tools:
                        print(f"✅ Found {len(github_tools)} GitHub tools")
                    else:
                        print("⚠️  No GitHub tools found - some tests may not trigger")
                else:
                    print(f"⚠️  Could not fetch tools: HTTP {response.status}")
        except Exception as e:
            print(f"⚠️  Error checking tools: {e}")
    
    print("\n" + "-" * 60)
    print("Testing error handling...\n")
    
    await test_mcp_error_handling()
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("- Tool errors should be returned as tool results, not HTTP 500")
    print("- The LLM should see the error and be able to explain it")
    print("- No uncaught exceptions should occur")

if __name__ == "__main__":
    asyncio.run(main())