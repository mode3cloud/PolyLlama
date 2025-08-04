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
from fastmcp import FastMCP
from fastmcp.client import Client
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
        self.proxies = {}
        self.server_tools = {}  # Store tool info for each server
        
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
            
            # Create proxy based on server type
            if config.url:
                # HTTP-based server (like personal-ai using mcp-remote)
                logger.info(f"   📡 HTTP endpoint: {config.url}")
                # For HTTP servers, create proxy from URL
                proxy = FastMCP.as_proxy(config.url, name=f"{server_name}_proxy")
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
                # Create proxy from transport
                proxy = FastMCP.as_proxy(transport, name=f"{server_name}_proxy")
            
            # Store the proxy
            self.proxies[server_name] = proxy
            
            # Test connection by creating a client temporarily
            if config.url:
                test_client = Client(config.url)
            else:
                test_transport = StdioTransport(
                    command=config.command,
                    args=config.args,
                    env=env if 'env' in locals() else None
                )
                test_client = Client(test_transport)
            
            async with test_client:
                # Try to list tools to verify connection
                try:
                    tools = await test_client.list_tools()
                    tool_count = len(tools)
                    server_info['tool_count'] = tool_count
                    server_info['status'] = 'connected'
                    
                    # Store tool information for later use
                    self.server_tools[server_name] = []
                    for tool in tools:
                        tool_info = {
                            'name': tool.name,
                            'description': tool.description,
                            'input_schema': getattr(tool, 'inputSchema', {})
                        }
                        self.server_tools[server_name].append(tool_info)
                    
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
        
        
    def get_proxies(self) -> Dict[str, Any]:
        """Get all proxy servers."""
        return self.proxies
    
    async def get_aggregated_tools(self) -> Dict[str, dict]:
        """Get all tools from all connected servers with prefixed names."""
        logger.info("Starting get_aggregated_tools")
        aggregated_tools = {}
        
        # Use the stored tool information from initialization
        for server_name, tools in self.server_tools.items():
            logger.info(f"Processing {len(tools)} tools from {server_name}")
            
            for tool_info in tools:
                prefixed_name = f"{server_name}__{tool_info['name']}"
                aggregated_tools[prefixed_name] = {
                    'name': tool_info['name'],
                    'description': tool_info['description'],
                    'server': server_name,
                    'input_schema': tool_info['input_schema']
                }
                logger.debug(f"Added tool: {prefixed_name}")
                
        logger.info(f"Aggregated {len(aggregated_tools)} tools total")
        return aggregated_tools
    
    async def call_tool(self, prefixed_tool_name: str, arguments: dict) -> Any:
        """Call a tool on the appropriate upstream server."""
        # Extract server name and tool name
        parts = prefixed_tool_name.split('__', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid tool name format: {prefixed_tool_name}")
            
        server_name, tool_name = parts
        
        if server_name not in self.servers:
            raise ValueError(f"Unknown server: {server_name}")
            
        try:
            # Create a client for this server
            config = self.servers[server_name]
            if config.url:
                client = Client(config.url)
            else:
                env = {**os.environ, **config.env} if config.env else None
                transport = StdioTransport(
                    command=config.command,
                    args=config.args,
                    env=env
                )
                client = Client(transport)
            
            async with client:
                # Call the tool
                result = await client.call_tool(tool_name, arguments)
                return result
                
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on server {server_name}: {e}")
            raise