"""
MCP Manager for LLM Proxy Service

Connects to the MCP Server Proxy and provides tool discovery/execution.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import aiohttp

logger = logging.getLogger(__name__)


# MCPServerConnection class removed - now using MCP Server Proxy instead


class MCPManager:
    """Connects to MCP Server Proxy and provides tool discovery/execution."""
    
    def __init__(self, proxy_url: str = "http://mcp-server:3001"):
        self.proxy_url = proxy_url
        self.tools_cache: List[Dict[str, Any]] = []
        self._initialized = False
        self._last_tools_fetch = 0
        self._tools_cache_duration = 60  # 1 minute cache
        
    async def initialize(self):
        """Initialize connection to MCP Server Proxy."""
        if self._initialized:
            return
            
        logger.info("Starting MCP Manager initialization (connecting to proxy)...")
        try:
            # Test connection to proxy
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.proxy_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        health_data = await response.json()
                        logger.info(f"Connected to MCP proxy: {health_data}")
                    else:
                        logger.warning(f"MCP proxy health check failed: {response.status}")
            
            # Refresh tools cache from proxy
            await self._refresh_tools_cache()
            self._initialized = True
            
            logger.info(f"MCP Manager initialized with {len(self.tools_cache)} tools from proxy")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP Manager: {e}")
    
    async def _refresh_tools_cache(self):
        """Refresh the tools cache from the MCP proxy."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.proxy_url}/info", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        tools = data.get("tools", [])
                        
                        # Convert to our expected format
                        self.tools_cache = []
                        for tool in tools:
                            # Extract server name from tool name (e.g., "github__search_repositories" -> "github")
                            server_name = tool["name"].split("__")[0] if "__" in tool["name"] else "unknown"
                            
                            self.tools_cache.append({
                                "name": tool["name"],
                                "description": tool["description"],
                                "inputSchema": {},  # Would need to get from MCP proxy if needed
                                "server": server_name
                            })
                        
                        self._last_tools_fetch = asyncio.get_event_loop().time()
                        logger.info(f"Refreshed tools cache: {len(self.tools_cache)} tools from proxy")
                    else:
                        logger.error(f"Failed to fetch tools from proxy: {response.status}")
        except Exception as e:
            logger.error(f"Failed to refresh tools cache: {e}")
    
    async def shutdown(self):
        """Shutdown MCP manager."""
        self.tools_cache = []
        self._initialized = False
        logger.info("MCP Manager shutdown complete")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from proxy."""
        if not self._initialized:
            await self.initialize()
        
        # Refresh cache if old
        now = asyncio.get_event_loop().time()
        if now - self._last_tools_fetch > self._tools_cache_duration:
            await self._refresh_tools_cache()
            
        return self.tools_cache
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool via the MCP proxy."""
        if not self._initialized:
            await self.initialize()
        
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "tool_execution",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.proxy_url}/mcp",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if "result" in result:
                            return result["result"]["content"]
                        else:
                            raise RuntimeError(f"Tool execution failed: {result.get('error', 'Unknown error')}")
                    else:
                        error_text = await response.text()
                        raise RuntimeError(f"HTTP {response.status}: {error_text}")
                        
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}': {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of MCP proxy connection."""
        return {
            "initialized": self._initialized,
            "servers": {},  # Will be populated by get_bridge_status
            "total_tools": len(self.tools_cache)
        }
    
    async def get_bridge_status(self, include_tools: bool = False) -> Dict[str, Any]:
        """Get detailed status from MCP proxy with optional tool information."""
        if not self._initialized:
            await self.initialize()
            
        servers = {}
        
        # Group tools by server name
        tools_by_server = {}
        for tool in self.tools_cache:
            server_name = tool["server"]
            if server_name not in tools_by_server:
                tools_by_server[server_name] = []
            tools_by_server[server_name].append(tool)
        
        # Create server status for each server with tools
        for server_name, tools in tools_by_server.items():
            server_info = {
                "connected": True,  # If we have tools, the server is connected
                "command": "npx",  # Default for MCP servers
                "args": [],
                "toolCount": len(tools),
                "lastError": None,
                "lastHealthCheck": self._last_tools_fetch
            }
            
            if include_tools:
                server_info["tools"] = tools
            
            servers[server_name] = server_info
        
        return {"servers": servers}
    
    def format_tools_for_llm(self, tool_selection: Optional[Dict[str, Dict[str, bool]]] = None) -> List[Dict[str, Any]]:
        """Format tools for LLM function calling, filtered by tool selection."""
        if not tool_selection:
            # If no selection provided, return all tools
            tools_to_format = self.tools_cache
        else:
            # Filter tools based on selection
            tools_to_format = []
            for tool in self.tools_cache:
                server_name = tool["server"]
                tool_name = tool["name"]
                
                # Check if this tool is selected
                if (server_name in tool_selection and 
                    tool_name in tool_selection[server_name] and 
                    tool_selection[server_name][tool_name]):
                    tools_to_format.append(tool)
        
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"]
                }
            }
            for tool in tools_to_format
        ]