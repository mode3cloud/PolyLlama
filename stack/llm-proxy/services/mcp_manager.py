"""
MCP Manager for LLM Proxy Service

Manages MCP server processes and provides tool discovery/execution.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPServerProcess:
    """Manages a single MCP server process."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self.read_stream = None
        self.write_stream = None
        self._transport = None
        
    async def start(self):
        """Start the MCP server process and connect to it."""
        try:
            # Build the command
            command = self.config.get("command", "")
            args = self.config.get("args", [])
            env = {**os.environ, **self.config.get("env", {})}
            
            # Create server parameters
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env
            )
            
            # Start the server - stdio_client returns an async context manager
            self._transport = stdio_client(server_params)
            transport_result = await self._transport.__aenter__()
            
            # Extract the read and write streams
            if isinstance(transport_result, tuple) and len(transport_result) == 2:
                self.read_stream, self.write_stream = transport_result
            else:
                raise ValueError(f"Unexpected transport result type: {type(transport_result)}")
            
            # Create and initialize the session
            self.session = ClientSession(self.read_stream, self.write_stream)
            await self.session.initialize()
            
            logger.info(f"Started MCP server '{self.name}' successfully")
            
        except Exception as e:
            logger.error(f"Failed to start MCP server '{self.name}': {e}")
            raise
    
    async def stop(self):
        """Stop the MCP server process."""
        if self.session:
            await self.session.close()
            self.session = None
        
        if self._transport:
            try:
                await self._transport.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing transport for '{self.name}': {e}")
            self._transport = None
            
        logger.info(f"Stopped MCP server '{self.name}'")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from this server."""
        if not self.session:
            return []
        
        try:
            result = await self.session.list_tools()
            tools = []
            for tool in result.tools:
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema.model_dump() if tool.inputSchema else {},
                    "server": self.name
                })
            return tools
        except Exception as e:
            logger.error(f"Failed to list tools from '{self.name}': {e}")
            return []
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on this server."""
        if not self.session:
            raise RuntimeError(f"Server '{self.name}' is not connected")
        
        try:
            result = await self.session.call_tool(tool_name, arguments)
            return result.content
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}' on '{self.name}': {e}")
            raise


class MCPManager:
    """Manages multiple MCP server processes."""
    
    def __init__(self, config_path: str = "/app/mcp-config.json"):
        self.config_path = config_path
        self.servers: Dict[str, MCPServerProcess] = {}
        self.tools_cache: List[Dict[str, Any]] = []
        self._initialized = False
        
    async def initialize(self):
        """Initialize MCP servers from configuration."""
        if self._initialized:
            return
            
        logger.info("Starting MCP Manager initialization...")
        try:
            # Load configuration
            config = await self._load_config()
            if not config:
                logger.warning("No MCP configuration found")
                return
            
            logger.info(f"Loaded MCP configuration with {len(config.get('mcpServers', {}))} servers")
            
            # Start each server with timeout
            mcp_servers = config.get("mcpServers", {})
            for server_name, server_config in mcp_servers.items():
                try:
                    server = MCPServerProcess(server_name, server_config)
                    # Use asyncio.wait_for with timeout to avoid blocking
                    await asyncio.wait_for(server.start(), timeout=10.0)
                    self.servers[server_name] = server
                    logger.info(f"Initialized MCP server: {server_name}")
                except asyncio.TimeoutError:
                    logger.error(f"Timeout starting MCP server '{server_name}' (10s)")
                except Exception as e:
                    logger.error(f"Failed to initialize MCP server '{server_name}': {e}")
            
            # Refresh tools cache
            await self._refresh_tools_cache()
            self._initialized = True
            
            logger.info(f"MCP Manager initialized with {len(self.servers)} servers and {len(self.tools_cache)} tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP Manager: {e}")
    
    async def _load_config(self) -> Optional[Dict[str, Any]]:
        """Load MCP configuration from file."""
        config_path = Path(self.config_path)
        if not config_path.exists():
            return None
        
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            return None
    
    async def _refresh_tools_cache(self):
        """Refresh the tools cache from all servers."""
        self.tools_cache = []
        for server_name, server in self.servers.items():
            tools = await server.list_tools()
            self.tools_cache.extend(tools)
    
    async def shutdown(self):
        """Shutdown all MCP servers."""
        for server_name, server in self.servers.items():
            try:
                await server.stop()
            except Exception as e:
                logger.error(f"Error stopping server '{server_name}': {e}")
        
        self.servers.clear()
        self.tools_cache = []
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
            if tool["name"] == tool_name:
                tool_info = tool
                break
        
        if not tool_info:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        server_name = tool_info["server"]
        server = self.servers.get(server_name)
        
        if not server:
            raise RuntimeError(f"Server '{server_name}' not available")
        
        return await server.execute_tool(tool_name, arguments)
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all MCP servers."""
        return {
            "initialized": self._initialized,
            "servers": {
                name: {
                    "connected": server.session is not None,
                    "command": server.config.get("command"),
                    "args": server.config.get("args", [])
                }
                for name, server in self.servers.items()
            },
            "total_tools": len(self.tools_cache)
        }
    
    def format_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Format tools for LLM function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"]
                }
            }
            for tool in self.tools_cache
        ]