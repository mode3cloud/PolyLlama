"""
MCP Bridge - Connects to upstream MCP servers and aggregates their tools
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import aiohttp
from fastmcp import FastMCP, Client
from fastmcp.client.transports import StdioTransport

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None  # For HTTP-based servers


class MCPBridge:
    """Bridges to upstream MCP servers and aggregates their tools."""
    
    def __init__(self):
        self.servers = {}
        self.clients = {}
        self.proxies = {}
        self.aggregated_tools = {}
        
    async def load_config(self, config_path: str) -> None:
        """Load MCP server configurations from file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            for server_name, server_config in config.get('mcpServers', {}).items():
                # Extract URL from args if it's an HTTP-based server
                url = None
                args = server_config.get('args', [])
                for arg in args:
                    if arg.startswith('http://') or arg.startswith('https://'):
                        url = arg
                        break
                
                self.servers[server_name] = MCPServerConfig(
                    name=server_name,
                    command=server_config.get('command', ''),
                    args=args,
                    env=server_config.get('env', {}),
                    url=url
                )
                logger.info(f"Loaded config for MCP server: {server_name}")
                
        except Exception as e:
            logger.error(f"Error loading MCP config: {e}")
            
    async def connect_server(self, server_name: str, config: MCPServerConfig) -> dict:
        """Connect to a single MCP server and return connection info."""
        server_info = {
            'name': server_name,
            'status': 'failed',
            'tool_count': 0,
            'error': None
        }
        
        try:
            logger.info(f"🔄 Initializing MCP server: {server_name}")
            logger.info(f"   Command: {config.command}")
            logger.info(f"   Args: {config.args}")
            
            # Create client based on server type
            if config.url:
                # HTTP-based server (like personal-ai using mcp-remote)
                logger.info(f"   📡 HTTP endpoint: {config.url}")
                # For HTTP servers, we use the URL directly
                client = Client(config.url)
            else:
                # STDIO-based server
                # Merge environment variables
                env = {**os.environ, **config.env} if config.env else None
                
                # Create STDIO transport
                transport = StdioTransport(
                    command=config.command,
                    args=config.args,
                    env=env
                )
                client = Client(transport)
            
            # Store the client
            self.clients[server_name] = client
            
            # Connect and test the client
            async with client:
                # Try to list tools to verify connection
                try:
                    tools = await client.list_tools()
                    tool_count = len(tools)
                    server_info['tool_count'] = tool_count
                    server_info['status'] = 'connected'
                    
                    # Create a proxy for this server
                    proxy = FastMCP.as_proxy(client, name=f"{server_name}_proxy")
                    self.proxies[server_name] = proxy
                    
                    logger.info(f"✅ Successfully connected to MCP server: {server_name} with {tool_count} tools")
                    
                except Exception as e:
                    server_info['error'] = f"Failed to list tools: {str(e)}"
                    logger.error(f"❌ Failed to list tools from {server_name}: {e}")
                    
        except Exception as e:
            server_info['error'] = str(e)
            logger.error(f"❌ Error connecting to {server_name}: {e}")
            
        return server_info
            
    async def connect_all_servers(self) -> Dict[str, dict]:
        """Connect to all configured MCP servers and return connection info."""
        servers_info = {}
        
        # Connect to servers with slight delay to avoid overwhelming the system
        for i, (server_name, config) in enumerate(self.servers.items()):
            if i > 0:
                await asyncio.sleep(0.5)  # Small delay between connections
            server_info = await self.connect_server(server_name, config)
            servers_info[server_name] = server_info
        
        logger.info(f"Initialized {len(self.servers)} MCP servers")
        return servers_info
        
    async def get_aggregated_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all tools from connected servers with server prefixes."""
        aggregated_tools = {}
        
        for server_name, client in self.clients.items():
            try:
                async with client:
                    tools = await client.list_tools()
                    
                    # Add tools with server prefix
                    for tool in tools:
                        # Use double underscore as separator
                        prefixed_name = f"{server_name}__{tool.name}"
                        aggregated_tools[prefixed_name] = {
                            'name': prefixed_name,
                            'description': tool.description,
                            'inputSchema': tool.inputSchema,
                            'server': server_name,
                            'original_name': tool.name
                        }
                        
            except Exception as e:
                logger.error(f"Error getting tools from {server_name}: {e}")
                
        self.aggregated_tools = aggregated_tools
        return aggregated_tools
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the appropriate MCP server."""
        if tool_name not in self.aggregated_tools:
            raise ValueError(f"Unknown tool: {tool_name}")
            
        tool_info = self.aggregated_tools[tool_name]
        server_name = tool_info['server']
        original_name = tool_info['original_name']
        
        if server_name not in self.clients:
            raise RuntimeError(f"Server {server_name} is not connected")
            
        client = self.clients[server_name]
        
        try:
            async with client:
                result = await client.call_tool(original_name, arguments)
                # Extract the content from the result
                if hasattr(result, 'content'):
                    return result.content
                return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise
            
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all aggregated tools."""
        return self.aggregated_tools