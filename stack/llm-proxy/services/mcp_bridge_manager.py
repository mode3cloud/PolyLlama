"""
MCP Bridge Manager for LLM Proxy Service

Uses HTTP bridge to communicate with MCP servers instead of direct stdio.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class MCPBridgeManager:
    """Manages MCP servers through HTTP bridge service."""
    
    def __init__(self, bridge_url: Optional[str] = None):
        self.bridge_url = bridge_url or os.getenv("MCP_BRIDGE_URL", "http://mcp-bridge:3000")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.tools_cache: List[Dict[str, Any]] = []
        self._initialized = False
        
    async def initialize(self):
        """Initialize connection to MCP bridge and refresh tools."""
        if self._initialized:
            return
            
        logger.info(f"Connecting to MCP Bridge at {self.bridge_url}")
        
        try:
            # Check bridge status
            response = await self.client.get(f"{self.bridge_url}/status")
            response.raise_for_status()
            
            status = response.json()
            logger.info(f"MCP Bridge status: {status}")
            
            # Refresh tools cache
            await self._refresh_tools_cache()
            self._initialized = True
            
            logger.info(f"MCP Bridge Manager initialized with {len(self.tools_cache)} tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP Bridge Manager: {e}")
            # Don't raise - allow service to start without MCP
    
    async def _refresh_tools_cache(self):
        """Refresh the tools cache from bridge."""
        try:
            response = await self.client.get(f"{self.bridge_url}/tools")
            response.raise_for_status()
            
            data = response.json()
            self.tools_cache = data.get("tools", [])
            logger.info(f"Refreshed tools cache: {len(self.tools_cache)} tools available")
            
        except Exception as e:
            logger.error(f"Failed to refresh tools cache: {e}")
            self.tools_cache = []
    
    async def shutdown(self):
        """Shutdown the bridge connection."""
        await self.client.aclose()
        self._initialized = False
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from all servers."""
        if not self._initialized:
            await self.initialize()
        return self.tools_cache
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on the appropriate server."""
        if not self._initialized:
            await self.initialize()
        
        # Find the tool and its server
        tool_info = None
        for tool in self.tools_cache:
            if tool.get("name") == tool_name:
                tool_info = tool
                break
        
        if not tool_info:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        server_name = tool_info.get("server")
        if not server_name:
            raise RuntimeError(f"No server found for tool '{tool_name}'")
        
        # Execute via bridge
        try:
            response = await self.client.post(
                f"{self.bridge_url}/execute",
                json={
                    "toolName": tool_name,
                    "arguments": arguments,
                    "server": server_name
                }
            )
            
            # Check if request was successful
            if response.status_code >= 400:
                # Try to extract error details from response body
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', f'HTTP {response.status_code} error')
                    
                    # Extract detailed error information if available
                    if isinstance(error_message, str) and 'Details:' in error_message:
                        # This is likely an MCP error with details
                        return f"Tool execution failed: {error_message}"
                    else:
                        return f"Tool execution failed: {error_message}"
                except:
                    # If we can't parse the error response, use status text
                    return f"Tool execution failed: HTTP {response.status_code} - {response.text}"
            
            response.raise_for_status()  # This shouldn't be reached if status >= 400
            
            result = response.json()
            if result.get("success"):
                return result.get("result")
            else:
                # Return error as result instead of raising exception
                error_msg = result.get('error', 'Unknown error')
                return f"Tool execution failed: {error_msg}"
                
        except httpx.HTTPStatusError as e:
            # HTTP error - extract details from response if available
            error_details = ""
            try:
                error_data = e.response.json()
                error_details = error_data.get('error', str(e))
            except:
                error_details = e.response.text or str(e)
            
            logger.error(f"HTTP error executing tool '{tool_name}': {error_details}")
            return f"Tool execution failed with HTTP {e.response.status_code}: {error_details}"
            
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}': {e}")
            # Return error message instead of raising
            return f"Tool execution failed with error: {str(e)}"
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of MCP bridge and servers."""
        return {
            "initialized": self._initialized,
            "bridge_url": self.bridge_url,
            "total_tools": len(self.tools_cache)
        }
    
    async def get_bridge_status(self) -> Dict[str, Any]:
        """Get detailed status from bridge."""
        try:
            response = await self.client.get(f"{self.bridge_url}/status")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get bridge status: {e}")
            return {"error": str(e)}
    
    def format_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Format tools for LLM function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {})
                }
            }
            for tool in self.tools_cache
        ]
    
    async def reinitialize(self):
        """Reinitialize the bridge connection and MCP servers."""
        try:
            response = await self.client.post(f"{self.bridge_url}/reinitialize")
            response.raise_for_status()
            
            # Reset state
            self._initialized = False
            self.tools_cache = []
            
            # Reinitialize
            await self.initialize()
            
        except Exception as e:
            logger.error(f"Failed to reinitialize MCP bridge: {e}")