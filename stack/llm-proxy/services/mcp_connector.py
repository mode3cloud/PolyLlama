"""
MCP Server Connector Module

Manages connections to multiple MCP servers with support for STDIO, SSE, and HTTP transports.
"""

import asyncio
import logging
import os
import shutil
from contextlib import AsyncExitStack
from typing import Dict, List, Any, Optional, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


class MCPConnector:
    """
    Manages connections to multiple MCP servers.
    
    Handles establishing connections to MCP servers via different transports
    and manages the tools provided by those servers.
    """
    
    def __init__(self):
        """Initialize the MCP Connector."""
        self.exit_stack = AsyncExitStack()
        self.sessions: Dict[str, Dict[str, Any]] = {}  # Server name -> session info
        self.available_tools: List[Dict[str, Any]] = []  # All tools from all servers
        self.enabled_tools: Dict[str, bool] = {}  # Tool name -> enabled status
        self.session_ids: Dict[str, str] = {}  # Server name -> session ID (for HTTP)
        self._initialized = False
        
    async def connect_to_servers(self, servers: List[Dict[str, Any]]) -> Tuple[dict, list, dict]:
        """
        Connect to multiple MCP servers.
        
        Args:
            servers: List of server configurations from discovery
            
        Returns:
            Tuple of (sessions, available_tools, enabled_tools)
        """
        if not servers:
            logger.warning("No servers to connect to")
            return self.sessions, self.available_tools, self.enabled_tools
        
        # Connect to each server
        connection_tasks = []
        for server in servers:
            connection_tasks.append(self._connect_to_server(server))
        
        # Wait for all connections to complete
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        # Log connection results
        successful = sum(1 for r in results if r is True)
        logger.info(f"Successfully connected to {successful}/{len(servers)} MCP servers")
        
        if not self.sessions:
            logger.error("Could not connect to any MCP servers")
        
        self._initialized = True
        return self.sessions, self.available_tools, self.enabled_tools
    
    async def _connect_to_server(self, server: Dict[str, Any]) -> bool:
        """
        Connect to a single MCP server.
        
        Args:
            server: Server configuration
            
        Returns:
            True if connection successful, False otherwise
        """
        server_name = server.get("name")
        server_type = server.get("type")
        
        logger.info(f"Connecting to MCP server: {server_name} (type: {server_type})")
        
        try:
            session = None
            
            if server_type == "stdio":
                # Connect via STDIO transport
                session = await self._connect_stdio_server(server)
            
            elif server_type == "sse":
                # Connect via SSE transport
                session = await self._connect_sse_server(server)
            
            elif server_type == "streamable_http":
                # For now, treat streamable_http similar to SSE
                # Full streamable HTTP support would require additional implementation
                logger.warning(f"Streamable HTTP support is limited, treating {server_name} as SSE")
                session = await self._connect_sse_server(server)
            
            else:
                logger.error(f"Unknown server type for {server_name}: {server_type}")
                return False
            
            if not session:
                logger.error(f"Failed to create session for {server_name}")
                return False
            
            # Initialize the session
            await session.initialize()
            
            # Store the session
            self.sessions[server_name] = {
                "session": session,
                "type": server_type,
                "tools": []
            }
            
            # Get tools from this server
            try:
                response = await session.list_tools()
                
                # Store tools with server namespace
                server_tools = []
                for tool in response.tools:
                    # Create namespaced tool name
                    namespaced_name = f"{server_name}__{tool.name}"
                    
                    # Store tool info
                    tool_info = {
                        "name": namespaced_name,
                        "original_name": tool.name,
                        "server": server_name,
                        "description": tool.description if hasattr(tool, 'description') else f"Tool from {server_name}",
                        "inputSchema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                    }
                    
                    server_tools.append(tool_info)
                    self.available_tools.append(tool_info)
                    self.enabled_tools[namespaced_name] = True  # Enable by default
                
                self.sessions[server_name]["tools"] = server_tools
                logger.info(f"Connected to {server_name} with {len(server_tools)} tools")
                
            except Exception as e:
                logger.warning(f"Failed to list tools for {server_name}: {e}")
                # Continue even if tool listing fails
            
            return True
            
        except FileNotFoundError as e:
            logger.error(f"File not found for {server_name}: {e}")
        except PermissionError as e:
            logger.error(f"Permission denied for {server_name}: {e}")
        except Exception as e:
            logger.error(f"Failed to connect to {server_name}: {e}", exc_info=True)
        
        return False
    
    async def _connect_stdio_server(self, server: Dict[str, Any]) -> Optional[ClientSession]:
        """
        Connect to a STDIO-based MCP server.
        
        Args:
            server: Server configuration
            
        Returns:
            ClientSession or None if connection failed
        """
        command = server.get("command", "npx")
        args = server.get("args", [])
        env = server.get("env", {})
        
        # Validate command exists
        if not shutil.which(command):
            # Special handling for node/npx in Docker
            if command in ["node", "npx"]:
                # Try common paths
                for path in ["/usr/bin/npx", "/usr/local/bin/npx"]:
                    if os.path.exists(path):
                        command = path
                        break
                else:
                    logger.error(f"Command '{command}' not found in PATH")
                    return None
            else:
                logger.error(f"Command '{command}' not found in PATH")
                return None
        
        # Create server parameters
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )
        
        # Connect via STDIO
        try:
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read_stream, write_stream = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            return session
            
        except Exception as e:
            logger.error(f"Failed to create STDIO session: {e}")
            return None
    
    async def _connect_sse_server(self, server: Dict[str, Any]) -> Optional[ClientSession]:
        """
        Connect to an SSE-based MCP server.
        
        Args:
            server: Server configuration
            
        Returns:
            ClientSession or None if connection failed
        """
        url = server.get("url")
        if not url:
            logger.error(f"No URL provided for SSE server {server.get('name')}")
            return None
        
        headers = server.get("headers", {})
        
        # Add MCP protocol version header
        headers["MCP-Protocol-Version"] = "2025-03-26"
        
        try:
            # Connect via SSE
            sse_transport = await self.exit_stack.enter_async_context(
                sse_client(url, headers=headers)
            )
            read_stream, write_stream = sse_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            return session
            
        except Exception as e:
            logger.error(f"Failed to create SSE session: {e}")
            return None
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool on the appropriate server.
        
        Args:
            tool_name: Namespaced tool name (e.g., "github__search_repositories")
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        # Parse server name and original tool name
        if "__" not in tool_name:
            raise ValueError(f"Invalid tool name format: {tool_name}")
        
        server_name, original_tool_name = tool_name.split("__", 1)
        
        # Find the server session
        if server_name not in self.sessions:
            raise ValueError(f"Unknown server: {server_name}")
        
        session_info = self.sessions[server_name]
        session = session_info["session"]
        
        # Execute the tool
        try:
            logger.debug(f"Executing tool {original_tool_name} on server {server_name}")
            result = await session.call_tool(original_tool_name, arguments)
            
            # Extract text content from result
            if hasattr(result, 'content') and result.content:
                # Handle array of content items
                if isinstance(result.content, list):
                    text_parts = []
                    for item in result.content:
                        if hasattr(item, 'text'):
                            text_parts.append(item.text)
                        elif hasattr(item, 'type') and item.type == 'text':
                            text_parts.append(getattr(item, 'text', str(item)))
                    return "\n".join(text_parts) if text_parts else str(result.content)
                else:
                    return str(result.content)
            
            return str(result)
            
        except Exception as e:
            logger.error(f"Failed to execute tool {tool_name}: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown all server connections."""
        logger.info("Shutting down MCP Connector...")
        
        # Close all connections via exit stack
        await self.exit_stack.aclose()
        
        # Clear all state
        self.sessions.clear()
        self.available_tools.clear()
        self.enabled_tools.clear()
        self.session_ids.clear()
        self._initialized = False
        
        logger.info("MCP Connector shutdown complete")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all server connections.
        
        Returns:
            Dictionary with connection status
        """
        return {
            "initialized": self._initialized,
            "total_servers": len(self.sessions),
            "total_tools": len(self.available_tools),
            "servers": {
                name: {
                    "connected": True,
                    "type": info["type"],
                    "tool_count": len(info["tools"])
                }
                for name, info in self.sessions.items()
            }
        }
    
    def get_tools_for_llm(self, tool_selection: Optional[Dict[str, bool]] = None) -> List[Dict[str, Any]]:
        """
        Format tools for LLM function calling.
        
        Args:
            tool_selection: Optional dict of tool_name -> enabled status
            
        Returns:
            List of tool definitions in OpenAI function format
        """
        tools_to_format = []
        
        if tool_selection:
            # Use provided selection
            for tool in self.available_tools:
                if tool_selection.get(tool["name"], False):
                    tools_to_format.append(tool)
        else:
            # Use all enabled tools
            for tool in self.available_tools:
                if self.enabled_tools.get(tool["name"], False):
                    tools_to_format.append(tool)
        
        # Format for OpenAI function calling
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