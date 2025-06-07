"""
MCP Client for LLM Proxy Service

HTTP client for communicating with the MCP Tools service.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MCPClient:
    """HTTP client for MCP Tools service."""
    
    def __init__(self, base_url: str):
        """Initialize MCP client.
        
        Args:
            base_url: Base URL of the MCP Tools service (e.g., http://localhost:8084)
        """
        self.base_url = base_url.rstrip("/")
        self.client: Optional[httpx.AsyncClient] = None
        self._connected = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def connect(self):
        """Connect to the MCP service."""
        if not self.client:
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(30.0)
            )
        
        # Test connection
        try:
            response = await self.client.get("/health")
            if response.status_code == 200:
                self._connected = True
                logger.info(f"Connected to MCP service at {self.base_url}")
            else:
                logger.warning(f"MCP service health check failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to connect to MCP service: {e}")
            self._connected = False
    
    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to MCP service."""
        return self._connected
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP service.
        
        Returns:
            List of tool definitions
        """
        if not self.client:
            await self.connect()
        
        try:
            # For now, we'll use the SSE endpoint to get tools
            # In the future, we should add a proper REST endpoint for tool listing
            response = await self.client.get("/tools")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to list tools: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool via the MCP service.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        if not self.client:
            await self.connect()
        
        try:
            # For now, we'll need to use the SSE interface
            # In the future, we should add proper REST endpoints for tool execution
            payload = {
                "tool": tool_name,
                "arguments": arguments
            }
            
            response = await self.client.post("/execute", json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"Tool execution failed: {response.status_code}"
                logger.error(error_msg)
                return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def get_tools_description(self) -> str:
        """Get a formatted description of all available tools.
        
        Returns:
            Formatted string describing all tools
        """
        tools = await self.list_tools()
        if not tools:
            return "No tools available from MCP service."
        
        descriptions = []
        for tool in tools:
            name = tool.get("name", "Unknown")
            description = tool.get("description", "No description")
            descriptions.append(f"- {name}: {description}")
        
        return "Available tools:\n" + "\n".join(descriptions)