"""
MCP Manager for LLM Proxy Service

Manages direct connections to MCP servers and provides tool discovery/execution.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .mcp_discovery import parse_mcp_config, get_server_display_info
from .mcp_connector import MCPConnector

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages direct connections to MCP servers and provides tool discovery/execution."""
    
    def __init__(self, config_path: str = "/app/mcp-config.json"):
        self.config_path = config_path
        self.connector = MCPConnector()
        self.tools_cache: List[Dict[str, Any]] = []
        self._initialized = False
        self._initialization_in_progress = False
        
    async def initialize(self):
        """Initialize connections to all MCP servers."""
        if self._initialized:
            return
        
        # Prevent concurrent initialization attempts
        if self._initialization_in_progress:
            logger.info("MCP initialization already in progress, skipping...")
            return
            
        self._initialization_in_progress = True
        
        try:
            logger.info("Starting MCP Manager initialization...")
            
            # Parse server configurations
            servers = parse_mcp_config(self.config_path)
            
            if not servers:
                logger.warning("No MCP servers configured")
                self._initialized = True
                return
            
            # Display server info
            server_info = get_server_display_info(servers)
            logger.info(f"Found {server_info['total']} MCP servers: {server_info['by_type']}")
            
            # Connect to all servers
            sessions, tools, enabled_tools = await self.connector.connect_to_servers(servers)
            
            # Update tools cache
            self.tools_cache = tools
            
            if self.tools_cache:
                self._initialized = True
                logger.info(f"MCP Manager initialized with {len(self.tools_cache)} tools from {len(sessions)} servers")
            else:
                self._initialized = True
                logger.warning("MCP Manager initialized but no tools available")
        
        except Exception as e:
            logger.error(f"Failed to initialize MCP Manager: {e}", exc_info=True)
            self._initialized = True  # Mark as initialized to prevent repeated attempts
        
        finally:
            self._initialization_in_progress = False
    
    
    async def shutdown(self):
        """Shutdown MCP manager."""
        await self.connector.shutdown()
        self.tools_cache = []
        self._initialized = False
        logger.info("MCP Manager shutdown complete")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools."""
        if not self._initialized:
            await self.initialize()
            
        return self.tools_cache
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool via direct server connection."""
        if not self._initialized:
            await self.initialize()
        
        try:
            return await self.connector.execute_tool(tool_name, arguments)
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}': {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of MCP connections."""
        status = self.connector.get_status() if self._initialized else {
            "initialized": False,
            "total_servers": 0,
            "total_tools": 0,
            "servers": {}
        }
        status["total_tools"] = len(self.tools_cache)
        return status
    
    async def get_bridge_status(self, include_tools: bool = False) -> Dict[str, Any]:
        """Get detailed status with optional tool information."""
        if not self._initialized:
            await self.initialize()
        
        status = self.connector.get_status()
        servers = {}
        
        # Group tools by server name
        tools_by_server = {}
        for tool in self.tools_cache:
            server_name = tool.get("server", "unknown")
            if server_name not in tools_by_server:
                tools_by_server[server_name] = []
            tools_by_server[server_name].append(tool)
        
        # Merge server status with tool information
        for server_name, server_info in status.get("servers", {}).items():
            servers[server_name] = {
                "connected": server_info.get("connected", False),
                "type": server_info.get("type", "unknown"),
                "toolCount": len(tools_by_server.get(server_name, [])),
                "lastError": None
            }
            
            if include_tools and server_name in tools_by_server:
                servers[server_name]["tools"] = tools_by_server[server_name]
        
        return {"servers": servers}
    
    def format_tools_for_llm(self, tool_selection: Optional[Dict[str, Dict[str, bool]]] = None) -> List[Dict[str, Any]]:
        """Format tools for LLM function calling, filtered by tool selection."""
        # Convert tool_selection format if needed
        flat_selection = None
        if tool_selection:
            flat_selection = {}
            for server_name, tools in tool_selection.items():
                for tool_name, enabled in tools.items():
                    flat_selection[tool_name] = enabled
        
        return self.connector.get_tools_for_llm(flat_selection)