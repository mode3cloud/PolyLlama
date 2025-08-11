"""
MCP Server Proxy - Exposes aggregated tools from multiple MCP servers as a single MCP server
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP, Context
from fastmcp.server import Server
from mcp_bridge import MCPBridge, MCPServerConfig

logger = logging.getLogger(__name__)


class MCPServerProxy:
    """Expose aggregated MCP tools as a unified MCP server."""
    
    def __init__(self, bridge: MCPBridge, name: str = "polyllama-mcp-proxy"):
        self.bridge = bridge
        self.mcp = FastMCP(name)
        self.tools_registered = False
        self._setup_metadata()
        
    def _setup_metadata(self):
        """Setup server metadata."""
        @self.mcp.meta.info
        def get_server_info() -> Dict[str, Any]:
            return {
                "name": "PolyLlama MCP Proxy",
                "version": "1.0.0",
                "description": "Unified MCP server aggregating multiple upstream MCP servers",
                "capabilities": {
                    "tools": True,
                    "resources": False,
                    "prompts": False
                }
            }
    
    async def setup_tools(self) -> None:
        """Register all aggregated tools with the MCP server."""
        if self.tools_registered:
            logger.info("Tools already registered, skipping setup")
            return
            
        logger.info("Setting up aggregated tools for MCP server proxy")
        tools = await self.bridge.get_aggregated_tools()
        
        for prefixed_name, tool_info in tools.items():
            # Create a closure to capture the tool name
            def create_tool_handler(tool_name: str, info: dict):
                # Get the input schema for this tool
                input_schema = info.get('input_schema', {})
                
                # Create a dynamic handler for this tool
                @self.mcp.tool(
                    name=tool_name,
                    description=f"[{info['server']}] {info['description']}"
                )
                async def handle_tool(context: Context, **kwargs) -> List[Dict[str, Any]]:
                    """Dynamic handler for aggregated tool."""
                    try:
                        logger.info(f"Executing tool {tool_name} with args: {kwargs}")
                        result = await self.bridge.call_tool(tool_name, kwargs)
                        
                        # Format result for MCP response
                        if isinstance(result, list):
                            return result
                        elif isinstance(result, dict):
                            return [{"type": "text", "text": json.dumps(result, indent=2)}]
                        else:
                            return [{"type": "text", "text": str(result)}]
                            
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}")
                        return [{"type": "text", "text": f"Error: {str(e)}"}]
                
                return handle_tool
            
            # Register the tool handler
            handler = create_tool_handler(prefixed_name, tool_info)
            logger.info(f"Registered tool: {prefixed_name}")
        
        self.tools_registered = True
        logger.info(f"Successfully registered {len(tools)} tools")
    
    async def start_stdio_server(self) -> None:
        """Start the MCP server in STDIO mode."""
        await self.setup_tools()
        logger.info("Starting MCP server proxy in STDIO mode")
        await self.mcp.run()
    
    async def start_http_server(self, host: str = "0.0.0.0", port: int = 3002) -> None:
        """Start the MCP server in HTTP mode."""
        await self.setup_tools()
        logger.info(f"Starting MCP server proxy in HTTP mode on {host}:{port}")
        
        # Create a FastMCP server with HTTP transport
        server = Server(self.mcp)
        await server.serve(host=host, port=port)
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the status of the proxy server."""
        tools = await self.bridge.get_aggregated_tools()
        servers_status = {}
        
        for server_name in self.bridge.servers:
            servers_status[server_name] = {
                "connected": server_name in self.bridge.proxies,
                "tool_count": len(self.bridge.server_tools.get(server_name, []))
            }
        
        return {
            "status": "running" if self.tools_registered else "not_initialized",
            "total_tools": len(tools),
            "servers": servers_status
        }


class ResilientMCPBridge(MCPBridge):
    """Enhanced MCP Bridge with resilience features."""
    
    def __init__(self):
        super().__init__()
        self.retry_configs = {}  # Store retry configurations per server
        self.connection_status = {}  # Track connection status
        
    async def connect_server_with_retry(
        self, 
        server_name: str, 
        config: MCPServerConfig,
        max_retries: int = 3,
        initial_delay: float = 1.0
    ) -> dict:
        """Connect to server with exponential backoff retry."""
        server_info = {
            'name': server_name,
            'status': 'failed',
            'tool_count': 0,
            'error': None,
            'retry_count': 0
        }
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Connection attempt {attempt + 1}/{max_retries} for {server_name}")
                result = await self.connect_server(server_name, config)
                
                if result['status'] == 'connected':
                    server_info.update(result)
                    self.connection_status[server_name] = 'connected'
                    logger.info(f"✅ Successfully connected to {server_name} on attempt {attempt + 1}")
                    return server_info
                    
            except Exception as e:
                server_info['retry_count'] = attempt + 1
                server_info['error'] = str(e)
                
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Connection failed for {server_name}, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to connect to {server_name} after {max_retries} attempts")
                    self.connection_status[server_name] = 'failed'
        
        return server_info
    
    async def hot_reload_server(self, server_name: str) -> dict:
        """Hot-reload a specific server without affecting others."""
        logger.info(f"Hot-reloading server: {server_name}")
        
        if server_name not in self.servers:
            return {
                'status': 'error',
                'error': f'Server {server_name} not found in configuration'
            }
        
        # Disconnect existing connection if present
        if server_name in self.proxies:
            logger.info(f"Disconnecting existing connection for {server_name}")
            del self.proxies[server_name]
            
        if server_name in self.server_tools:
            del self.server_tools[server_name]
        
        # Reconnect with retry
        config = self.servers[server_name]
        result = await self.connect_server_with_retry(server_name, config)
        
        return {
            'status': 'reloaded' if result['status'] == 'connected' else 'failed',
            'server_info': result
        }
    
    async def connect_all_servers(self) -> Dict[str, dict]:
        """Connect to all servers with resilience."""
        servers_info = {}
        
        # Connect to servers concurrently with retry
        tasks = []
        for server_name, config in self.servers.items():
            task = self.connect_server_with_retry(server_name, config)
            tasks.append((server_name, task))
        
        # Wait for all connections with timeout
        for server_name, task in tasks:
            try:
                server_info = await asyncio.wait_for(task, timeout=30.0)
                servers_info[server_name] = server_info
            except asyncio.TimeoutError:
                logger.error(f"Timeout connecting to {server_name}")
                servers_info[server_name] = {
                    'name': server_name,
                    'status': 'timeout',
                    'error': 'Connection timeout after 30 seconds'
                }
        
        # Log summary
        connected = sum(1 for info in servers_info.values() if info['status'] == 'connected')
        failed = len(servers_info) - connected
        logger.info(f"Connection summary: {connected} connected, {failed} failed out of {len(servers_info)} servers")
        
        return servers_info
    
    def get_connection_status(self) -> Dict[str, str]:
        """Get current connection status for all servers."""
        return self.connection_status.copy()


class EnhancedToolManager:
    """Enhanced tool management with enable/disable and grouping."""
    
    def __init__(self):
        self.enabled_tools = {}  # Tool name -> enabled status
        self.tool_groups = {}    # Server -> list of tools
        self.tool_metadata = {}  # Tool name -> metadata
        self.tool_usage_stats = {}  # Tool name -> usage statistics
        
    def initialize_from_bridge(self, bridge: MCPBridge):
        """Initialize tool manager from bridge's aggregated tools."""
        for server_name, tools in bridge.server_tools.items():
            self.tool_groups[server_name] = []
            
            for tool in tools:
                prefixed_name = f"{server_name}__{tool['name']}"
                self.tool_groups[server_name].append(prefixed_name)
                self.enabled_tools[prefixed_name] = True  # Enable by default
                self.tool_metadata[prefixed_name] = {
                    'server': server_name,
                    'original_name': tool['name'],
                    'description': tool['description'],
                    'input_schema': tool.get('input_schema', {})
                }
                self.tool_usage_stats[prefixed_name] = {
                    'call_count': 0,
                    'success_count': 0,
                    'error_count': 0,
                    'total_duration_ms': 0
                }
    
    def set_tool_enabled(self, tool_name: str, enabled: bool) -> bool:
        """Enable or disable a specific tool."""
        if tool_name in self.enabled_tools:
            self.enabled_tools[tool_name] = enabled
            logger.info(f"Tool {tool_name} {'enabled' if enabled else 'disabled'}")
            return True
        return False
    
    def set_server_tools_enabled(self, server_name: str, enabled: bool) -> int:
        """Enable or disable all tools from a specific server."""
        count = 0
        for tool_name in self.tool_groups.get(server_name, []):
            if self.set_tool_enabled(tool_name, enabled):
                count += 1
        logger.info(f"{'Enabled' if enabled else 'Disabled'} {count} tools from server {server_name}")
        return count
    
    def get_enabled_tools(self) -> List[str]:
        """Get list of enabled tool names."""
        return [name for name, enabled in self.enabled_tools.items() if enabled]
    
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Get enabled tools formatted for LLM consumption."""
        tools = []
        for tool_name, enabled in self.enabled_tools.items():
            if enabled and tool_name in self.tool_metadata:
                metadata = self.tool_metadata[tool_name]
                tools.append({
                    'name': tool_name,
                    'description': metadata['description'],
                    'parameters': metadata['input_schema']
                })
        return tools
    
    def record_tool_usage(
        self, 
        tool_name: str, 
        success: bool, 
        duration_ms: float
    ):
        """Record tool usage statistics."""
        if tool_name in self.tool_usage_stats:
            stats = self.tool_usage_stats[tool_name]
            stats['call_count'] += 1
            if success:
                stats['success_count'] += 1
            else:
                stats['error_count'] += 1
            stats['total_duration_ms'] += duration_ms
    
    def get_tool_statistics(self) -> Dict[str, Any]:
        """Get aggregated tool usage statistics."""
        server_stats = {}
        
        for server_name in self.tool_groups:
            server_stats[server_name] = {
                'total_calls': 0,
                'success_rate': 0.0,
                'avg_duration_ms': 0.0,
                'tools': []
            }
            
            for tool_name in self.tool_groups[server_name]:
                if tool_name in self.tool_usage_stats:
                    stats = self.tool_usage_stats[tool_name]
                    server_stats[server_name]['total_calls'] += stats['call_count']
                    
                    if stats['call_count'] > 0:
                        success_rate = stats['success_count'] / stats['call_count']
                        avg_duration = stats['total_duration_ms'] / stats['call_count']
                    else:
                        success_rate = 0.0
                        avg_duration = 0.0
                    
                    server_stats[server_name]['tools'].append({
                        'name': tool_name,
                        'enabled': self.enabled_tools.get(tool_name, False),
                        'call_count': stats['call_count'],
                        'success_rate': success_rate,
                        'avg_duration_ms': avg_duration
                    })
        
        return server_stats


# Example usage
async def main():
    """Example of how to use the MCP Server Proxy."""
    # Create resilient bridge
    bridge = ResilientMCPBridge()
    
    # Load configuration
    await bridge.load_config('/path/to/mcp-config.json')
    
    # Connect to all servers with retry
    servers_info = await bridge.connect_all_servers()
    
    # Create tool manager
    tool_manager = EnhancedToolManager()
    tool_manager.initialize_from_bridge(bridge)
    
    # Create and start the MCP server proxy
    proxy = MCPServerProxy(bridge)
    
    # Start in HTTP mode for other clients to connect
    await proxy.start_http_server(host="0.0.0.0", port=3002)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())